"""RAG cực đơn giản — không embedding, không vector DB, 2 tầng dữ liệu.

- data/index.json: file ROUTING nhẹ (build_index.py sinh ra) — mỗi thủ tục
  chỉ có tên, mã, slug, danh sách TÊN section (không có nội dung). Load
  toàn bộ vào RAM lúc server khởi động, cực nhanh vì rất nhỏ.
- data/procedures/<slug>.json: nội dung ĐẦY ĐỦ của MỘT thủ tục. Chỉ đọc từ
  đĩa khi đã xác định đúng thủ tục cần tra (tránh tải hết mọi thủ tục vào
  RAM ngay từ đầu khi số lượng PDF tăng lên).

Search 2 bước, không cần một lệnh gọi API embedding nào (giữ đúng tinh
thần "không tốn thêm token của AI" cho việc tra cứu):
1. Chọn thủ tục nào trong index routing khớp query nhất (keyword scoring).
2. Trong thủ tục đó, chọn section nào khớp nhất, trả nội dung section đó.
"""

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

_MIN_MATCH_RATIO = 0.3  # ít nhất 30% từ khóa distinct của query phải khớp

# Alias cho tiêu đề section — người dùng hỏi bằng lời nói tự nhiên thường
# không dùng đúng từ trong tiêu đề PDF chính thức (ví dụ nói "giấy tờ" thay
# vì "HỒ SƠ", "bao lâu" thay vì "THỜI HẠN GIẢI QUYẾT"). Không có alias thì
# _tokenize(title) không khớp được câu hỏi thật, luôn thua các section dài
# khác chỉ vì chúng tình cờ chứa nhiều từ trùng nội dung hơn.
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


# Load một lần khi module được import (lúc server start) — chỉ file routing
# nhẹ, không đọc bất kỳ file procedures/*.json nào cho tới khi search().
_ROUTING_INDEX: list[dict] = _load_routing_index()


def reload_index() -> None:
    """Nạp lại index routing từ đĩa — gọi sau khi build_index.py chạy lại
    (ví dụ ngay sau khi upload một PDF mới qua giao diện) mà không cần
    khởi động lại server."""
    global _ROUTING_INDEX
    _ROUTING_INDEX = _load_routing_index()


def get_routing_index() -> list[dict]:
    """Trả bản sao index routing đang có trong RAM — dùng cho trang quản
    lý liệt kê thủ tục (GET /procedures), không đọc lại đĩa."""
    return list(_ROUTING_INDEX)


def _load_procedure_detail(slug: str) -> dict | None:
    path = PROCEDURES_DIR / f"{slug}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


class SearchResult:
    """Kết quả một lần tra cứu — TÁCH RIÊNG phần cho AI nói (text tự nhiên,
    Gemini dùng làm căn cứ trả lời bằng giọng) khỏi phần cho giao diện hiển
    thị (structured, dữ liệu có cấu trúc thật từ dossier_cases đã parse sẵn
    — không đoán/parse ngược lại từ lời AI nói, vốn không đáng tin cậy)."""

    def __init__(self, text_for_ai: str, structured: dict | None = None) -> None:
        self.text_for_ai = text_for_ai
        self.structured = structured


def search_procedure(query: str, max_chars: int = 2000) -> SearchResult:
    """Tìm thủ tục + section liên quan nhất tới `query`.

    Bước 1 chọn thủ tục (dùng file routing nhẹ, không đọc nội dung); bước 2
    mới đọc đúng 1 file chi tiết của thủ tục đã chọn để chọn section. Chỉ
    một lần đọc/tính toán cục bộ (không gọi Gemini) — không cần gọi 2 lần,
    cả text cho AI lẫn dữ liệu card cho UI lấy chung từ đây.
    """
    if not _ROUTING_INDEX:
        return SearchResult("Không có dữ liệu thủ tục nào được nạp trong hệ thống.")

    query_words = _tokenize(query)
    if not query_words:
        return SearchResult("Không tìm thấy thông tin phù hợp.")

    # Bước 1: chọn thủ tục — khớp theo tên + mã, không cần đọc nội dung.
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

    # Bước 2: trong thủ tục đã chọn, tìm section khớp nhất — ưu tiên khớp
    # TIÊU ĐỀ section rất mạnh (x10): các section dài (ví dụ "TRÌNH TỰ THỰC
    # HIỆN") tình cờ chứa nhiều từ trùng nội dung hơn dù không phải section
    # người dùng thực sự muốn hỏi, nên phần content chỉ dùng để phá thế hòa.
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

    # Dữ liệu card cho UI: chỉ có khi section là "THÀNH PHẦN HỒ SƠ" (đã parse
    # cấu trúc dossier_cases ở build_index.py) — các section khác (trình tự,
    # căn cứ pháp lý...) hiện chỉ có text thô, chưa đáng để dựng card riêng.
    structured = None
    if best_section.get("dossier_cases"):
        structured = {
            "type": "dossier",
            "procedure_name": detail["procedure_name"],
            "source_url": source_url,
            "cases": best_section["dossier_cases"],
        }

    return SearchResult(text_for_ai, structured)
