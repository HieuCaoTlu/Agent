import json
from pathlib import Path

from app import text_model
from app.extension_bridge import extension_manager

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


def get_cached(cache_key: str) -> dict | None:
    return _load_cache().get(cache_key)


async def scan_raw(fallback_key: str | None = None, known_url: str | None = None) -> tuple[str, dict]:
    if known_url:
        cached = get_cached(known_url)
        if cached and cached.get("items"):
            return known_url, cached

    page = await extension_manager.send_command("scan_required_documents", {})
    items = page.get("items") or []
    cache_key = page.get("url") or known_url or fallback_key or "unknown"

    cache = _load_cache()
    existing = cache.get(cache_key)
    if existing and existing.get("summary"):
        return cache_key, existing

    result = {"items": items, "summary": None}
    cache[cache_key] = result
    _save_cache()
    return cache_key, result


async def summarize(fallback_key: str | None = None, known_url: str | None = None) -> dict:
    cache_key, raw = await scan_raw(fallback_key, known_url)
    if raw.get("summary"):
        return raw

    items = raw.get("items") or []
    if not items:
        result = {"items": [], "summary": []}
        _load_cache()[cache_key] = result
        _save_cache()
        return result

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

    result = {"items": [], "summary": summary}
    _load_cache()[cache_key] = result
    _save_cache()
    return result
