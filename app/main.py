import asyncio
import shutil
import sys
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

import build_index
from app import dom_ai
from app import submit_flow
from app import text_model
from app import voice_provider
from app.conversation_log import ConversationLogger
from app.extension_bridge import ExtensionCommandError, ExtensionNotConnected, extension_manager
from app.rag import get_routing_index, reload_index

SUBMIT_PROVINCE = "Thành phố Hà Nội"
SUBMIT_WARD = "Yên Sở"

app = FastAPI()

_background_tasks: set[asyncio.Task] = set()
_voice_session_active = False


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


async def _handle_submit_procedure(
    websocket: WebSocket,
    history: list[tuple[str, str]],
    log: ConversationLogger,
    procedure_name: str | None = None,
) -> None:
    for attempt in range(1, _MAX_SUBMIT_ATTEMPTS + 1):
        is_last_attempt = attempt == _MAX_SUBMIT_ATTEMPTS
        if attempt > 1:
            log.submit_action("retry_attempt", {"attempt": attempt})
            await websocket.send_json(
                {"type": "submit_procedure_status", "message": f"Đang thử lại lần {attempt}/{_MAX_SUBMIT_ATTEMPTS}..."}
            )
        ok = await _attempt_submit_procedure(websocket, history, log, procedure_name, report_error=is_last_attempt)
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

        await websocket.send_json(
            {"type": "submit_procedure_status", "message": "Đang điền tỉnh/phường..."}
        )
        await asyncio.sleep(1.5)
        flow_result = await extension_manager.send_command(
            "run_fixed_submit_flow", {"province": SUBMIT_PROVINCE, "ward": SUBMIT_WARD}
        )
        log.submit_action("run_fixed_submit_flow_done", flow_result)

        await websocket.send_json(
            {
                "type": "submit_procedure_done",
                "message": "Đã điền sẵn tỉnh/phường. Vui lòng tự bấm \"Nộp trực tuyến\" và đăng nhập để hoàn tất.",
            }
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
    global _voice_session_active
    await websocket.accept()
    if _voice_session_active:
        await websocket.send_json(
            {"type": "submit_procedure_error", "message": "Đã có một phiên trợ lý giọng nói khác đang hoạt động."}
        )
        await websocket.close()
        return
    _voice_session_active = True

    log = ConversationLogger()
    history: list[tuple[str, str]] = []

    def on_submit_procedure(procedure_name: str | None) -> None:
        _track_task(_handle_submit_procedure(websocket, history, log, procedure_name=procedure_name))

    try:
        await voice_provider.run_voice_session(websocket, log, history, on_submit_procedure)
    finally:
        log.session_end()
        _voice_session_active = False


@app.websocket("/extension")
async def extension_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    await extension_manager.register(websocket)
    try:
        while True:
            message = await websocket.receive_json()
            await extension_manager.handle_response(message)
    except WebSocketDisconnect:
        pass
    finally:
        extension_manager.unregister(websocket)


@app.get("/procedures")
async def list_procedures() -> list[dict]:
    return get_routing_index()


@app.delete("/procedures/{slug}")
async def delete_procedure(slug: str) -> dict:
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
    file: UploadFile = File(...), source_url: str = Form(default="")
) -> dict:
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


app.mount("/", StaticFiles(directory="static", html=True), name="static")
