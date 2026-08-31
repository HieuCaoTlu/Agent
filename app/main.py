import asyncio
import os
import shutil
import sys
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import build_index
from app import auth
from app import dom_ai
from app import procedure_index
from app import required_documents
from app import submit_flow
from app import text_model
from app import voice_provider
from app.conversation_log import ConversationLogger
from app.extension_bridge import ExtensionCommandError, ExtensionNotConnected, extension_manager
from app.rag import get_routing_index, reload_index
from app.submit_flow import SUBMIT_PROVINCE, SUBMIT_WARD

app = FastAPI()

_FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "")
if _FRONTEND_ORIGIN:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[_FRONTEND_ORIGIN],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

_ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
_MAX_CONCURRENT_SESSIONS = int(os.getenv("MAX_CONCURRENT_SESSIONS", "1"))

_background_tasks: set[asyncio.Task] = set()
_active_session_count = 0


def _check_ws_token(websocket: WebSocket) -> bool:
    return auth.verify_token(websocket.query_params.get("token")) is not None


def _require_admin(x_admin_password: str | None) -> None:
    if not _ADMIN_PASSWORD or x_admin_password != _ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Sai mật khẩu quản trị.")


def _track_task(coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


async def _extract_procedure_name(history: list[tuple[str, str]]) -> str | None:
    if not history:
        return None

    transcript = "\n".join(f"{who}: {text}" for who, text in history)
    prompt = (
        "Đây là đoạn hội thoại giữa người dùng và trợ lý giọng nói về thủ "
        "tục hành chính:\n\n"
        f"{transcript}\n\n"
        "Người dùng vừa yêu cầu nộp hồ sơ. Hãy trả về CHÍNH XÁC tên thủ tục "
        "hành chính đang được nhắc tới (ví dụ: \"Đăng ký khai sinh\"), "
        "không kèm giải thích, không kèm dấu ngoặc kép. Nếu không xác định "
        "được thủ tục nào, trả về đúng chữ KHONG_RO."
    )

    response_text = await text_model.generate_text(prompt)
    name = response_text.strip()
    if not name or name == "KHONG_RO":
        return None
    return name


_MAX_SUBMIT_ATTEMPTS = 3


async def _handle_scan_form_fields(
    websocket: WebSocket,
    history: list[tuple[str, str]],
    log: ConversationLogger,
    session_state: dict,
) -> dict:
    try:
        log.submit_action("scan_form_with_comboboxes_start")
        await websocket.send_json({"type": "submit_procedure_status", "message": "Đang quét trang hiện tại..."})
        page = await extension_manager.send_command("scan_form_with_comboboxes", {}, timeout=60.0)
        combobox_options = page.get("combobox_options") or []
        log.submit_action(
            "scan_form_with_comboboxes_result",
            {
                "url": page.get("url"),
                "html_length": len(page.get("html") or ""),
                "combobox_count": len(combobox_options),
                "combobox_options": combobox_options,
            },
        )

        log.submit_action("analyze_form_start")
        await websocket.send_json({"type": "submit_procedure_status", "message": "Đang phân tích các trường cần điền..."})
        analysis = await dom_ai.analyze_form(page["html"], combobox_options)
        fields = analysis.get("fields") or []
        session_state["last_scanned_fields"] = fields
        log.submit_action("scan_form_fields", {"fields_count": len(fields), "fields": fields})
        # Chỉ trả label rút gọn cho Gemini Live (không phải selector/options đầy đủ) —
        # tool_response quá dài (nhiều field, mỗi field kèm selector dài) từng gây lỗi
        # 1011 Internal error từ Gemini Live. Bản đầy đủ đã lưu ở session_state phía trên.
        _MAX_LABELS = 15
        labels = [f.get("label", "") for f in fields]
        return {
            "fields_count": len(fields),
            "sample_labels": labels[:_MAX_LABELS],
            "truncated": len(labels) > _MAX_LABELS,
        }
    except Exception as exc:
        log.submit_error("scan_form_fields", repr(exc))
        return {"error": str(exc)}


async def _handle_ai_fill_fields(
    websocket: WebSocket,
    history: list[tuple[str, str]],
    log: ConversationLogger,
    session_state: dict,
    pending_user_text: str = "",
) -> dict:
    fields = session_state.get("last_scanned_fields") or []
    if not fields:
        return {"ok": False, "message": "Chưa quét được thông tin trang hiện tại, cần quét lại trang trước."}

    transcript = "\n".join(f"{who}: {text}" for who, text in history)
    if pending_user_text.strip():
        transcript += f"\nNgười dùng: {pending_user_text.strip()}"

    def _field_line(f: dict) -> str:
        field_type = f.get("field_type", "text")
        line = f'- selector="{f["selector"]}" label="{f["label"]}" field_type="{field_type}"'
        options = f.get("options")
        if field_type == "combobox" and options:
            line += f' (CHỈ được chọn value đúng 1 trong các lựa chọn thật sau: {", ".join(options)})'
        elif field_type == "choice_option":
            line += (
                ' (đây là MỘT lựa chọn cụ thể trong nhóm radio/checkbox — nếu muốn chọn '
                'lựa chọn này thì trả về value="chọn", không cần trả về field khác cùng '
                'nhóm mà không muốn chọn)'
            )
        return line

    fields_text = "\n".join(_field_line(f) for f in fields)
    schema = {
        "type": "OBJECT",
        "properties": {
            "values": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "selector": {"type": "STRING"},
                        "value": {"type": "STRING"},
                    },
                    "required": ["selector", "value"],
                },
            },
        },
        "required": ["values"],
    }
    prompt = (
        "Đây là danh sách các trường cần điền trên trang form hồ sơ hành "
        f"chính:\n{fields_text}\n\n"
        f'Người dùng đang cư trú tại "{SUBMIT_WARD}, {SUBMIT_PROVINCE}" — nếu '
        "có trường liên quan tỉnh/thành phố hoặc phường/xã cư trú thì điền "
        "đúng 2 giá trị này. Đoạn hội thoại giữa người dùng và trợ lý:\n\n"
        f"{transcript}\n\n"
        "Chỉ trả về những trường mà bạn XÁC ĐỊNH CHẮC CHẮN giá trị (từ thông "
        "tin tỉnh/phường ở trên hoặc từ những gì người dùng đã tự nói ra "
        "trong hội thoại) — KHÔNG suy đoán hay bịa giá trị cho các trường "
        "còn lại (họ tên, CCCD, ngày sinh... nếu người dùng chưa từng nói). "
        "Với field_type là combobox có ghi kèm danh sách lựa chọn thật, value "
        "trả về PHẢI là một trong các lựa chọn đó nguyên văn, không được viết "
        "khác đi. Với field_type là choice_option, mỗi selector là MỘT lựa "
        "chọn cụ thể trong nhóm radio/checkbox — chỉ trả về đúng field muốn "
        "bấm chọn (value ghi \"chọn\"), không trả về các field khác cùng "
        "nhóm mà không muốn chọn."
    )
    log.submit_action("ai_fill_fields_start", {"fields_count": len(fields)})
    await websocket.send_json({"type": "submit_procedure_status", "message": "Đang xác định giá trị cần điền..."})
    result = await text_model.generate_json(prompt, schema)
    values = result.get("values") or []
    log.submit_action("ai_fill_fields_decided", {"values": values})

    field_by_selector = {f["selector"]: f for f in fields}
    filled = []
    for item in values:
        selector = item.get("selector")
        value = item.get("value")
        field = field_by_selector.get(selector)
        if not field or not value:
            continue
        log.submit_action("fill_field_start", {"selector": selector, "label": field["label"], "value": value})
        await websocket.send_json(
            {"type": "submit_procedure_status", "message": f'Đang điền "{field["label"]}"...'}
        )
        try:
            await extension_manager.send_command(
                "fill_field",
                {
                    "selector": selector,
                    "value": value,
                    "field_type": field.get("field_type", "text"),
                },
            )
            filled.append(field["label"])
            log.submit_action("fill_field_done", {"selector": selector, "label": field["label"], "value": value})
        except Exception as exc:
            log.submit_error("fill_field", repr(exc))

    remaining = [f["label"] for f in fields if f["label"] not in filled]
    log.submit_action("ai_fill_fields_result", {"filled": filled, "remaining_count": len(remaining)})
    # Rút gọn danh sách trả cho Gemini Live — với form nhiều trường (vd 57), remaining
    # có thể rất dài và từng gây lỗi 500 InternalServerError từ Gemini Live khi turn quá dài.
    _MAX_LIST = 15
    return {
        "ok": True,
        "filled": filled[:_MAX_LIST],
        "filled_count": len(filled),
        "remaining_sample": remaining[:_MAX_LIST],
        "remaining_count": len(remaining),
    }


async def _handle_get_required_documents(
    websocket: WebSocket,
    log: ConversationLogger,
    session_state: dict,
    inject_queue: asyncio.Queue = None,
) -> None:
    log.submit_action("get_required_documents_start")
    await websocket.send_json({"type": "submit_procedure_status", "message": "Đang tóm tắt thành phần hồ sơ..."})
    try:
        result = await required_documents.summarize(
            session_state.get("procedure_name"), known_url=session_state.get("known_url")
        )
        session_state["required_documents"] = result
        log.submit_action("get_required_documents_done", {"summary_count": len(result.get("summary") or [])})
        await websocket.send_json({"type": "required_documents", "data": result})
        if inject_queue is not None:
            summary = result.get("summary") or []
            if summary:
                _MAX_ITEMS = 8
                sample = "; ".join(summary[:_MAX_ITEMS])
                suffix = f" (và {len(summary) - _MAX_ITEMS} giấy tờ khác)" if len(summary) > _MAX_ITEMS else ""
                await inject_queue.put(
                    f"Hệ thống vừa tra được {len(summary)} loại giấy tờ cần chuẩn bị, ví dụ: "
                    f"{sample}{suffix}. Hãy đọc lại khái quát cho người dùng nghe (người dùng "
                    "cũng đang nhìn thấy danh sách đầy đủ trên màn hình nên không cần đọc "
                    "hết từng thứ)."
                )
            else:
                await inject_queue.put(
                    "Hệ thống không tìm thấy thông tin thành phần hồ sơ trên trang hiện "
                    "tại, hãy báo người dùng biết điều này."
                )
    except Exception as exc:
        log.submit_error("get_required_documents", repr(exc))
        await websocket.send_json(
            {"type": "submit_procedure_error", "message": f"Không quét được thành phần hồ sơ: {exc}"}
        )


async def _handle_submit_procedure(
    websocket: WebSocket,
    history: list[tuple[str, str]],
    log: ConversationLogger,
    procedure_name: str | None = None,
    inject_queue: asyncio.Queue = None,
    session_state: dict = None,
) -> None:
    for attempt in range(1, _MAX_SUBMIT_ATTEMPTS + 1):
        is_last_attempt = attempt == _MAX_SUBMIT_ATTEMPTS
        if attempt > 1:
            log.submit_action("retry_attempt", {"attempt": attempt})
            await websocket.send_json(
                {"type": "submit_procedure_status", "message": f"Đang thử lại lần {attempt}/{_MAX_SUBMIT_ATTEMPTS}..."}
            )
        ok = await _attempt_submit_procedure(
            websocket,
            history,
            log,
            procedure_name,
            report_error=is_last_attempt,
            inject_queue=inject_queue,
            session_state=session_state,
        )
        if ok:
            return
        if not is_last_attempt:
            await asyncio.sleep(1.5)


async def _attempt_submit_procedure(
    websocket: WebSocket,
    history: list[tuple[str, str]],
    log: ConversationLogger,
    procedure_name: str | None,
    report_error: bool,
    inject_queue: asyncio.Queue = None,
    session_state: dict = None,
) -> bool:
    try:
        if procedure_name:
            log.submit_action("extract_procedure_name", {"procedure_name": procedure_name, "source": "manual"})
        else:
            procedure_name = await _extract_procedure_name(history)
            log.submit_action("extract_procedure_name", {"procedure_name": procedure_name, "source": "gemini"})
        if not procedure_name:
            await websocket.send_json(
                {"type": "submit_procedure_error", "message": "Không xác định được thủ tục cần nộp."}
            )
            return True

        known_url: str | None = None

        candidates = procedure_index.lookup_candidates(procedure_name)
        log.submit_action("procedure_index_lookup", {"candidates_count": len(candidates)})

        if candidates:
            href = await procedure_index.pick_variant_href(procedure_name, candidates)
            log.submit_action("procedure_index_pick", {"href": href})
            if href:
                detail_url = "https://dichvucong.gov.vn" + href
                known_url = detail_url
                await websocket.send_json({"type": "submit_procedure_status", "message": "Đang mở trang thủ tục..."})
                await extension_manager.send_command("open_url_and_scan", {"url": detail_url})
                log.submit_action("open_detail_url_done", {"url": detail_url})
            else:
                candidates = []

        if not candidates:
            await websocket.send_json({"type": "submit_procedure_status", "message": f"Đang tìm kiếm: {procedure_name}..."})
            search_url = submit_flow.build_search_url(procedure_name)
            results_page = await extension_manager.send_command("open_url_and_scan", {"url": search_url})
            log.submit_action("open_search_url", {"url": search_url})

            await websocket.send_json({"type": "submit_procedure_status", "message": "Đang chọn đúng thủ tục..."})
            pick = await dom_ai.pick_search_result(results_page["html"], procedure_name)
            log.submit_action("pick_search_result", pick)
            if not pick.get("result_selector"):
                log.submit_action("pick_search_result_retry")
                await asyncio.sleep(2.0)
                results_page = await extension_manager.send_command("scan_current_page", {})
                pick = await dom_ai.pick_search_result(results_page["html"], procedure_name)
                log.submit_action("pick_search_result_retry_result", pick)
            if not pick.get("result_selector"):
                log.submit_error("pick_search_result", "result_selector rỗng — Gemini không chọn được kết quả nào.")
                await websocket.send_json(
                    {"type": "submit_procedure_error", "message": "Không tìm thấy thủ tục trên dichvucong.gov.vn."}
                )
                return True
            await extension_manager.send_command("click_selector", {"selector": pick["result_selector"]})
            log.submit_action("click_search_result_done", {"selector": pick["result_selector"]})

        if session_state is not None:
            session_state["procedure_name"] = procedure_name
            session_state["known_url"] = known_url
            log.submit_action("scan_required_documents_start", {"procedure_name": procedure_name})
            await websocket.send_json(
                {"type": "submit_procedure_status", "message": "Đang lưu lại thành phần hồ sơ cần chuẩn bị..."}
            )
            try:
                _, raw_docs = await required_documents.scan_raw(procedure_name, known_url=known_url)
                log.submit_action(
                    "scan_required_documents_done",
                    {"items_count": len(raw_docs.get("items") or [])},
                )
            except Exception as exc:
                log.submit_error("scan_required_documents", repr(exc))

        await websocket.send_json(
            {"type": "submit_procedure_status", "message": "Đang điền tỉnh/phường..."}
        )
        await asyncio.sleep(1.5)
        flow_result = await extension_manager.send_command(
            "run_fixed_submit_flow", {"province": SUBMIT_PROVINCE, "ward": SUBMIT_WARD}
        )
        log.submit_action("run_fixed_submit_flow_done", flow_result)

        done_message = (
            "Đã điền sẵn tỉnh/phường. Vui lòng tự bấm \"Nộp trực tuyến\" và đăng nhập để bắt đầu nộp."
        )
        await websocket.send_json({"type": "submit_procedure_done", "message": done_message})
        await websocket.send_json({"type": "show_scan_form_button"})
        if inject_queue is not None:
            await inject_queue.put(
                "Hệ thống đã tìm thấy hồ sơ và điền sẵn tỉnh/phường xong. Hãy thông báo ngắn gọn cho "
                "người dùng là đã tìm thấy hồ sơ, nhắc họ tự bấm nút \"Nộp trực tuyến\" trên màn hình "
                "và đăng nhập bằng tài khoản định danh điện tử (VNeID) — đây chỉ là bước bắt đầu nộp "
                "trực tuyến, sau đó người dùng vẫn cần tự điền tiếp thông tin, đính kèm giấy tờ và ký "
                "số theo hướng dẫn trên trang."
            )
        return True
    except ExtensionNotConnected:
        log.submit_error("extension_connection", "Chưa cài hoặc chưa kết nối tiện ích mở rộng trình duyệt.")
        if report_error:
            await websocket.send_json(
                {
                    "type": "submit_procedure_error",
                    "message": "Chưa cài hoặc chưa kết nối tiện ích mở rộng trình duyệt.",
                }
            )
        return False
    except TimeoutError:
        log.submit_error("timeout", "Tiện ích mở rộng không phản hồi kịp thời (quá 20s).")
        if report_error:
            await websocket.send_json(
                {"type": "submit_procedure_error", "message": "Tiện ích mở rộng không phản hồi kịp thời."}
            )
        return False
    except ExtensionCommandError as exc:
        log.submit_error("extension_command", str(exc))
        if report_error:
            await websocket.send_json(
                {"type": "submit_procedure_error", "message": f"Lỗi thao tác trên trang: {exc}"}
            )
        return False
    except Exception as exc:
        log.submit_error("unexpected", repr(exc))
        if report_error:
            await websocket.send_json(
                {"type": "submit_procedure_error", "message": f"Lỗi không xác định: {exc}"}
            )
        return False


@app.websocket("/ws")
async def voice_ws(websocket: WebSocket) -> None:
    global _active_session_count
    await websocket.accept()

    if not _check_ws_token(websocket):
        await websocket.close(code=4401, reason="unauthorized")
        return

    if _active_session_count >= _MAX_CONCURRENT_SESSIONS:
        await websocket.send_json(
            {"type": "submit_procedure_error", "message": "Hệ thống đang bận, vui lòng thử lại sau ít phút."}
        )
        await websocket.close()
        return
    _active_session_count += 1

    log = ConversationLogger()
    history: list[tuple[str, str]] = []
    inject_queue: asyncio.Queue = asyncio.Queue()
    session_state: dict = {}

    def on_submit_procedure(procedure_name: str | None) -> None:
        _track_task(
            _handle_submit_procedure(
                websocket,
                history,
                log,
                procedure_name=procedure_name,
                inject_queue=inject_queue,
                session_state=session_state,
            )
        )

    async def on_scan_form_fields() -> dict:
        return await _handle_scan_form_fields(websocket, history, log, session_state)

    async def on_ai_fill_fields(pending_user_text: str = "") -> dict:
        return await _handle_ai_fill_fields(websocket, history, log, session_state, pending_user_text)

    def on_get_required_documents() -> None:
        _track_task(_handle_get_required_documents(websocket, log, session_state, inject_queue))

    try:
        await voice_provider.run_voice_session(
            websocket,
            log,
            history,
            on_submit_procedure,
            on_scan_form_fields,
            on_ai_fill_fields,
            on_get_required_documents,
            inject_queue,
        )
    finally:
        log.session_end()
        _active_session_count -= 1


@app.get("/extension/status")
async def extension_status() -> dict:
    return {"connected": extension_manager.is_connected}


_EXTENSION_PING_TIMEOUT = 40.0


@app.websocket("/extension")
async def extension_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    if not _check_ws_token(websocket):
        await websocket.close(code=4401, reason="unauthorized")
        return
    await extension_manager.register(websocket)
    try:
        while True:
            message = await asyncio.wait_for(websocket.receive_json(), timeout=_EXTENSION_PING_TIMEOUT)
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            await extension_manager.handle_response(message)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        extension_manager.unregister(websocket)


@app.get("/procedures")
async def list_procedures() -> list[dict]:
    return get_routing_index()


@app.delete("/procedures/{slug}")
async def delete_procedure(slug: str, x_admin_password: str | None = Header(default=None)) -> dict:
    _require_admin(x_admin_password)
    entry = next((e for e in get_routing_index() if e["slug"] == slug), None)
    if entry is None:
        return {"ok": False, "error": "Không tìm thấy thủ tục cần xóa."}

    pdf_path = Path("data/pdfs") / entry["source_file"]
    url_path = pdf_path.with_suffix(pdf_path.suffix + ".url.txt")
    detail_path = Path("data/procedures") / f"{slug}.json"

    for path in (pdf_path, url_path, detail_path):
        if path.exists():
            path.unlink()

    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    build_index.build()
    reload_index()

    return {"ok": True}


@app.post("/upload-pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    source_url: str = Form(default=""),
    x_admin_password: str | None = Header(default=None),
) -> dict:
    _require_admin(x_admin_password)
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return {"ok": False, "error": "Chỉ chấp nhận file .pdf"}

    dest_dir = Path("data/pdfs")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / file.filename
    with dest_path.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    source_url = source_url.strip()
    url_path = dest_path.with_suffix(dest_path.suffix + ".url.txt")
    if source_url:
        url_path.write_text(source_url, encoding="utf-8")
    elif url_path.exists():
        url_path.unlink()

    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    build_index.build()
    reload_index()

    return {"ok": True, "saved_as": str(dest_path), "source_url": source_url or None}


class AuthLoginRequest(BaseModel):
    username: str


@app.post("/auth/login")
async def auth_login(body: AuthLoginRequest, request: Request) -> dict:
    username = body.username.strip()
    if not username or not auth.is_valid_username(username):
        raise HTTPException(status_code=401, detail="Username không hợp lệ hoặc chưa được cấp quyền.")

    token = auth.issue_token(username)
    host = request.headers.get("host", request.url.netloc)
    ws_scheme = "wss" if request.url.scheme == "https" else "ws"
    web_link = f"{request.url.scheme}://{host}/?token={token}"
    extension_url = f"{ws_scheme}://{host}/extension?token={token}"
    return {
        "ok": True,
        "token": token,
        "expires_in_seconds": auth.JWT_TTL_SECONDS,
        "web_link": web_link,
        "extension_url": extension_url,
    }


class AdminLoginRequest(BaseModel):
    password: str


@app.post("/admin/login")
async def admin_login(body: AdminLoginRequest) -> dict:
    if not _ADMIN_PASSWORD or body.password != _ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Sai mật khẩu.")
    return {"ok": True, "usernames": auth.list_users()}


class AdminUserRequest(BaseModel):
    username: str


@app.post("/admin/users")
async def admin_add_user(body: AdminUserRequest, x_admin_password: str | None = Header(default=None)) -> dict:
    _require_admin(x_admin_password)
    username = body.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username không được để trống.")
    return {"ok": True, "usernames": auth.add_user(username)}


@app.delete("/admin/users/{username}")
async def admin_remove_user(username: str, x_admin_password: str | None = Header(default=None)) -> dict:
    _require_admin(x_admin_password)
    return {"ok": True, "usernames": auth.remove_user(username)}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
