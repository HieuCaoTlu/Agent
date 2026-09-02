import os
import shutil
import sys
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import build_index
from app import procedure_index
from app import required_documents
from app import voice_provider
from app.conversation_log import ConversationLogger
from app.rag import get_routing_index, reload_index

_FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "")
_ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
_MAX_CONCURRENT_SESSIONS = int(os.getenv("MAX_CONCURRENT_SESSIONS", "1"))

_active_session_count = 0

app = FastAPI()

if _FRONTEND_ORIGIN:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[_FRONTEND_ORIGIN],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _require_admin(x_admin_password: str | None) -> None:
    if not _ADMIN_PASSWORD or x_admin_password != _ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Sai mật khẩu quản trị.")


_FALLBACK_SUBMISSION_STEPS = [
    "Xác định đúng thủ tục hành chính cần thực hiện.",
    "Chuẩn bị đầy đủ thành phần hồ sơ theo danh sách được tra cứu.",
    "Mở đúng trang thủ tục trên dichvucong.gov.vn, đăng nhập bằng tài khoản định danh điện tử (VNeID) rồi bấm \"Nộp trực tuyến\".",
    "Điền thông tin, đính kèm giấy tờ, ký số theo hướng dẫn trên trang và theo dõi kết quả xử lý.",
]


async def _resolve_procedure(procedure_name: str, log: ConversationLogger) -> tuple[str, str | None]:
    candidates = procedure_index.lookup_candidates(procedure_name)
    log.submit_action("procedure_index_lookup", {"query": procedure_name, "candidates_count": len(candidates)})
    if not candidates:
        return procedure_name, None

    href = await procedure_index.pick_variant_href(procedure_name, candidates)
    log.submit_action("procedure_index_pick", {"href": href})
    if not href:
        return procedure_name, None

    matched = next((c for c in candidates if c["href"] == href), None)
    resolved_name = matched["name"] if matched else procedure_name
    detail_url = "https://dichvucong.gov.vn" + href
    return resolved_name, detail_url


async def _handle_show_required_documents(
    websocket: WebSocket,
    log: ConversationLogger,
    procedure_name: str,
) -> dict:
    log.submit_action("show_required_documents_start", {"procedure_name": procedure_name})
    try:
        resolved_name, known_url = await _resolve_procedure(procedure_name, log)
        result = await required_documents.summarize(resolved_name, known_url=known_url)
        await websocket.send_json(
            {
                "type": "procedure_info",
                "data": {
                    "procedure_name": resolved_name,
                    "href": result.get("href") or known_url,
                    "items": result.get("items") or [],
                    "summary": result.get("summary") or [],
                },
            }
        )
        summary = result.get("summary") or []
        log.submit_action("show_required_documents_done", {"summary_count": len(summary)})
        if not summary:
            return {
                "ok": True,
                "found": False,
                "message": "Chưa có dữ liệu thành phần hồ sơ cho thủ tục này, sẽ được cập nhật sau.",
            }
        _MAX_ITEMS = 8
        return {
            "ok": True,
            "found": True,
            "procedure_name": resolved_name,
            "summary_sample": summary[:_MAX_ITEMS],
            "summary_count": len(summary),
        }
    except Exception as exc:
        log.submit_error("show_required_documents", repr(exc))
        return {"ok": False, "error": str(exc)}


async def _handle_show_submission_steps(
    websocket: WebSocket,
    log: ConversationLogger,
    procedure_name: str,
) -> dict:
    log.submit_action("show_submission_steps_start", {"procedure_name": procedure_name})
    try:
        resolved_name, known_url = await _resolve_procedure(procedure_name, log)
        result = await required_documents.summarize_steps(resolved_name, known_url=known_url)
        steps = result.get("steps_summary") or _FALLBACK_SUBMISSION_STEPS
        online_fee = required_documents.get_online_fee(resolved_name)

        await websocket.send_json(
            {
                "type": "submission_steps",
                "data": {
                    "procedure_name": resolved_name,
                    "href": result.get("href") or known_url,
                    "steps": steps,
                    "online_fee": online_fee,
                },
            }
        )
        log.submit_action("show_submission_steps_done", {"href": known_url, "steps_count": len(steps)})
        return {
            "ok": True,
            "procedure_name": resolved_name,
            "has_link": bool(known_url),
            "steps_count": len(steps),
            "online_fee": (online_fee or {}).get("fee") or "chưa rõ",
            "processing_time": (online_fee or {}).get("time_text") or "chưa rõ",
        }
    except Exception as exc:
        log.submit_error("show_submission_steps", repr(exc))
        return {"ok": False, "error": str(exc)}


@app.websocket("/ws")
async def voice_ws(websocket: WebSocket) -> None:
    global _active_session_count
    await websocket.accept()

    if _active_session_count >= _MAX_CONCURRENT_SESSIONS:
        await websocket.send_json(
            {"type": "session_error", "message": "Hệ thống đang bận, vui lòng thử lại sau ít phút."}
        )
        await websocket.close()
        return
    _active_session_count += 1

    log = ConversationLogger()
    history: list[tuple[str, str]] = []

    async def on_show_required_documents(procedure_name: str) -> dict:
        return await _handle_show_required_documents(websocket, log, procedure_name)

    async def on_show_submission_steps(procedure_name: str) -> dict:
        return await _handle_show_submission_steps(websocket, log, procedure_name)

    try:
        await voice_provider.run_voice_session(
            websocket,
            log,
            history,
            on_show_required_documents,
            on_show_submission_steps,
        )
    finally:
        log.session_end()
        _active_session_count -= 1


@app.get("/procedures")
async def list_procedures() -> list[dict]:
    return get_routing_index()


@app.get("/required-documents")
async def list_required_documents() -> list[dict]:
    cache = required_documents.list_all()
    return [
        {
            "name": name,
            "href": entry.get("href"),
            "items_count": len(entry.get("items") or []),
            "has_summary": bool(entry.get("summary")),
        }
        for name, entry in cache.items()
    ]


@app.get("/required-documents/{name}")
async def get_required_documents_detail(name: str) -> dict:
    entry = required_documents.get_cached(name)
    if entry is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy thủ tục.")
    return {"name": name, **entry}


@app.post("/required-documents/{name}/summarize")
async def summarize_required_documents(name: str) -> dict:
    entry = required_documents.get_cached(name)
    if entry is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy thủ tục.")
    result = await required_documents.summarize(name, known_url=entry.get("href"))
    return {"name": name, **result}


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


class AdminLoginRequest(BaseModel):
    password: str


@app.post("/admin/login")
async def admin_login(body: AdminLoginRequest) -> dict:
    if not _ADMIN_PASSWORD or body.password != _ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Sai mật khẩu.")
    return {"ok": True}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
