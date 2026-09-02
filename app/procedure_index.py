import json
import math
import re
from pathlib import Path

from app import text_model

_INDEX_PATH = Path("data/procedure_flat_index.json")

_STOPWORDS = {
    "là", "và", "của", "cho", "khi", "để", "các", "một", "có", "trong",
    "được", "về", "này", "thì", "hoặc", "như", "gì", "tôi", "bạn", "cần",
    "muốn", "làm", "sao", "ạ", "vậy", "với", "người", "thủ", "tục",
}

_index: list[dict] | None = None
_doc_freq: dict[str, int] | None = None


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[\wÀ-ỹ]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 1}


def reload() -> None:
    global _index, _doc_freq
    _index = None
    _doc_freq = None


def _load() -> list[dict]:
    global _index, _doc_freq
    if _index is None:
        if _INDEX_PATH.exists():
            _index = json.loads(_INDEX_PATH.read_text(encoding="utf-8"))
        else:
            _index = []
        _doc_freq = {}
        for entry in _index:
            for word in _tokenize(entry["name"]):
                _doc_freq[word] = _doc_freq.get(word, 0) + 1
    return _index


def _word_weight(word: str) -> float:
    total_docs = max(len(_index or []), 1)
    freq = (_doc_freq or {}).get(word, 1)
    return math.log(total_docs / freq + 1)


def lookup_candidates(procedure_name: str) -> list[dict]:
    index = _load()
    if not index:
        return []
    query_words = _tokenize(procedure_name)
    if not query_words:
        return []

    scored = []
    for entry in index:
        entry_words = _tokenize(entry["name"])
        overlap = query_words & entry_words
        if not overlap:
            continue
        score = sum(_word_weight(w) for w in overlap)
        scored.append((score, entry))

    if not scored:
        return []

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score = scored[0][0]
    return [entry for score, entry in scored if score >= best_score * 0.6][:15]


async def pick_variant_href(procedure_name: str, candidates: list[dict]) -> str | None:
    if len(candidates) == 1:
        return candidates[0]["href"]

    schema = {
        "type": "OBJECT",
        "properties": {
            "href": {"type": "STRING", "nullable": True},
        },
        "required": ["href"],
    }
    options_text = "\n".join(f'- href="{c["href"]}": {c["name"]}' for c in candidates)
    prompt = (
        f'Người dùng cần nộp hồ sơ thủ tục "{procedure_name}". Dưới đây là danh sách '
        "các thủ tục thật có sẵn khớp gần đúng (mỗi dòng là 1 thủ tục với href riêng):\n\n"
        f"{options_text}\n\n"
        "Chọn ĐÚNG 1 href khớp nhất với ý định của người dùng (nếu người dùng không "
        "nói rõ yếu tố nước ngoài/lưu động/lại thì ưu tiên thủ tục thông thường, đơn "
        "giản nhất). Trả về đúng href đó. Nếu không thủ tục nào phù hợp, trả null."
    )
    result = await text_model.generate_json(prompt, schema)
    return result.get("href")
