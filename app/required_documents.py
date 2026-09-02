import json
from pathlib import Path

from app import text_model

_CACHE_PATH = Path("data/required_documents_cache.json")

_cache: dict[str, dict] | None = None


def _load_cache() -> dict[str, dict]:
    global _cache
    if _cache is None:
        if _CACHE_PATH.exists():
            _cache = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        else:
            _cache = {}
    return _cache


def _save_cache() -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_PATH.write_text(json.dumps(_cache, ensure_ascii=False, indent=2), encoding="utf-8")


def reload() -> None:
    global _cache
    _cache = None


def get_cached(cache_key: str) -> dict | None:
    return _load_cache().get(cache_key)


def list_all() -> dict[str, dict]:
    global _cache
    _cache = None  # luôn đọc lại từ disk — scheduler/script khảo sát ngoài process có thể vừa ghi mới
    return _load_cache()


def get_raw(procedure_name: str, known_url: str | None = None) -> dict:
    cache = _load_cache()
    entry = cache.get(procedure_name)
    if entry:
        return entry
    return {"href": known_url, "items": [], "summary": None}


async def summarize(procedure_name: str, known_url: str | None = None) -> dict:
    cache = _load_cache()
    raw = cache.get(procedure_name)
    if raw is None:
        return {"href": known_url, "items": [], "summary": []}
    if raw.get("summary"):
        return raw

    items = raw.get("items") or []
    if not items:
        raw["summary"] = []
        cache[procedure_name] = raw
        _save_cache()
        return raw

    schema = {
        "type": "OBJECT",
        "properties": {
            "summary": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
            },
        },
        "required": ["summary"],
    }
    items_text = "\n".join(
        f"- {item['name']} (số lượng: {item.get('qty') or 'không rõ'})" for item in items
    )
    prompt = (
        "Đây là danh sách các giấy tờ cần chuẩn bị cho một thủ tục hành chính, "
        f"kèm số lượng/loại cần nộp (bản chính hoặc bản sao):\n{items_text}\n\n"
        "Hãy tóm tắt lại thành danh sách ngắn gọn, mỗi mục chỉ 1 câu ngắn, dễ hiểu "
        "với người dân bình thường, PHẢI giữ rõ số lượng và loại (bản chính/bản sao) "
        "đi kèm mỗi giấy tờ (bỏ bớt phần trích dẫn luật/điều khoản dài dòng, chỉ giữ "
        "tên giấy tờ, số lượng/loại, và điều kiện quan trọng nếu có)."
    )
    result_json = await text_model.generate_json(prompt, schema)
    summary = result_json.get("summary") or [
        f"{item['name']} ({item.get('qty') or 'không rõ số lượng'})" for item in items
    ]

    # Giữ nguyên items — không xóa sau khi có summary, để vẫn tra được bản đầy
    # đủ (vd trang "Thành phần hồ sơ" liệt kê toàn bộ văn bản) song song bản
    # tóm tắt ngắn cho AI đọc bằng giọng nói.
    raw["summary"] = summary
    cache[procedure_name] = raw
    _save_cache()
    return raw


def get_online_fee(procedure_name: str) -> dict | None:
    entry = _load_cache().get(procedure_name)
    if not entry:
        return None
    methods = entry.get("methods") or []
    online = next((m for m in methods if "trực tuyến" in (m.get("method") or "").lower()), None)
    if not online:
        return None

    # "time" chỉ đôi khi chứa số ngày (vd "1") — nhiều thủ tục để "-" và ghi
    # thời hạn xử lý thật trong "description" thay vào đó (vị trí không đồng
    # nhất giữa các thủ tục), nên gộp cả 2 làm 1 chuỗi hiển thị đầy đủ.
    time_part = online.get("time") or ""
    if time_part and time_part != "-":
        time_part = f"{time_part} ngày"
    else:
        time_part = ""
    description = " ".join((online.get("description") or "").split())
    time_text = " — ".join(p for p in (time_part, description) if p)

    return {**online, "time_text": time_text}


async def summarize_steps(procedure_name: str, known_url: str | None = None) -> dict:
    cache = _load_cache()
    raw = cache.get(procedure_name)
    if raw is None:
        return {"href": known_url, "steps": [], "steps_summary": []}
    if raw.get("steps_summary"):
        return raw

    steps = raw.get("steps") or []
    if not steps:
        raw["steps_summary"] = []
        cache[procedure_name] = raw
        _save_cache()
        return raw

    schema = {
        "type": "OBJECT",
        "properties": {
            "steps_summary": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
            },
        },
        "required": ["steps_summary"],
    }
    steps_text = "\n".join(f"- {s}" for s in steps)
    prompt = (
        "Đây là trình tự thực hiện đầy đủ (nguyên văn quy định) của một thủ tục "
        f"hành chính, áp dụng cho cả nộp trực tiếp lẫn trực tuyến:\n{steps_text}\n\n"
        "Hãy tóm tắt lại thành các bước ngắn gọn, dễ hiểu, CHỈ tập trung vào "
        "luồng nộp hồ sơ TRỰC TUYẾN qua Cổng dịch vụ công (bỏ qua các đoạn chỉ "
        "áp dụng cho nộp trực tiếp), mỗi bước 1 câu ngắn, giữ đúng thứ tự thực "
        "hiện, bỏ bớt phần trích dẫn căn cứ pháp lý/số hiệu văn bản dài dòng."
    )
    result_json = await text_model.generate_json(prompt, schema)
    steps_summary = result_json.get("steps_summary") or steps

    raw["steps_summary"] = steps_summary
    cache[procedure_name] = raw
    _save_cache()
    return raw
