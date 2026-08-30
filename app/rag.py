import json
import re
from pathlib import Path

INDEX_PATH = Path("data/index.json")
PROCEDURES_DIR = Path("data/procedures")

_STOPWORDS = {
    "là", "và", "của", "cho", "khi", "để", "các", "một", "có", "trong",
    "được", "về", "này", "thì", "hoặc", "như", "gì", "tôi", "bạn", "cần",
    "muốn", "làm", "sao", "ạ", "vậy", "the", "a", "an",
}

_MIN_MATCH_RATIO = 0.3

_SECTION_ALIASES: dict[str, set[str]] = {
    "THÀNH PHẦN HỒ SƠ": {"giấy", "tờ", "chuẩn", "bị", "mang", "nộp", "cần", "gồm"},
    "CÁCH THỨC THỰC HIỆN": {"phí", "lệ", "nộp", "đâu", "online", "trực", "tuyến", "bưu", "điện", "bao", "lâu", "ngày"},
    "CĂN CỨ PHÁP LÝ": {"luật", "nghị", "định", "thông", "tư", "quy", "định", "văn", "bản"},
    "TRÌNH TỰ THỰC HIỆN": {"quy", "trình", "bước", "thế", "nào", "làm"},
    "KẾT QUẢ XỬ LÝ": {"kết", "quả", "nhận", "được", "gì"},
}


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[\wÀ-ỹ]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 1}


def _load_routing_index() -> list[dict]:
    if not INDEX_PATH.exists():
        return []
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


_ROUTING_INDEX: list[dict] = _load_routing_index()


def reload_index() -> None:
    global _ROUTING_INDEX
    _ROUTING_INDEX = _load_routing_index()


def get_routing_index() -> list[dict]:
    return list(_ROUTING_INDEX)


def _load_procedure_detail(slug: str) -> dict | None:
    path = PROCEDURES_DIR / f"{slug}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


class SearchResult:
    def __init__(self, text_for_ai: str, structured: dict | None = None) -> None:
        self.text_for_ai = text_for_ai
        self.structured = structured


def search_procedure(query: str, max_chars: int = 2000) -> SearchResult:
    if not _ROUTING_INDEX:
        return SearchResult("Không có dữ liệu thủ tục nào được nạp trong hệ thống.")

    query_words = _tokenize(query)
    if not query_words:
        return SearchResult("Không tìm thấy thông tin phù hợp.")

    best_procedure = None
    best_score = 0
    for entry in _ROUTING_INDEX:
        haystack = _tokenize(entry["procedure_name"] + " " + (entry.get("procedure_code") or ""))
        matched = query_words & haystack
        if not matched:
            continue
        score = len(matched)
        if score > best_score:
            best_score = score
            best_procedure = entry

    if best_procedure is None or (best_score / len(query_words)) < _MIN_MATCH_RATIO:
        return SearchResult("Không tìm thấy thủ tục phù hợp trong dữ liệu hiện có.")

    detail = _load_procedure_detail(best_procedure["slug"])
    if detail is None:
        return SearchResult("Không tìm thấy thủ tục phù hợp trong dữ liệu hiện có.")

    best_section = None
    best_section_score = -1.0
    for section in detail["sections"]:
        title_words = _tokenize(section["title"]) | _SECTION_ALIASES.get(section["title"], set())
        content_words = _tokenize(section["content"])
        score = len(query_words & title_words) * 10 + len(query_words & content_words)
        if score > best_section_score:
            best_section_score = score
            best_section = section

    if best_section is None:
        return SearchResult("Không tìm thấy thông tin phù hợp trong dữ liệu thủ tục hiện có.")

    header = f"[{detail['procedure_name']} — {best_section['title']}]"
    footer = ""
    source_url = detail.get("source_url")
    if source_url:
        footer = f"\n(Nguồn: {source_url})"

    budget = max_chars - len(header) - len(footer)
    content = best_section["content"][: max(budget, 0)]
    text_for_ai = f"{header}\n{content}{footer}"

    structured = None
    if best_section.get("dossier_cases"):
        structured = {
            "type": "dossier",
            "procedure_name": detail["procedure_name"],
            "source_url": source_url,
            "cases": best_section["dossier_cases"],
        }

    return SearchResult(text_for_ai, structured)
