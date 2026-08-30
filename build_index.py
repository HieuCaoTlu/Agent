"""Script build index RAG — chạy THỦ CÔNG khi có PDF mới, KHÔNG chạy lúc
server khởi động (đọc/parse PDF là việc tốn thời gian, không cần lặp lại
mỗi lần start nếu dữ liệu chưa đổi).

Sinh ra 2 TẦNG dữ liệu, tách riêng theo mục đích:

- data/index.json: file ROUTING nhẹ — mỗi thủ tục chỉ có tên, mã, file
  nguồn và DANH SÁCH TÊN section (không có nội dung). Dùng để quyết định
  "nên tra thủ tục nào" mà không phải tải nội dung đầy đủ.
- data/procedures/<slug>.json: MỘT file riêng cho MỘT thủ tục, chứa đầy đủ
  nội dung từng section. Chỉ đọc file này khi đã biết chính xác thủ tục
  cần tra (từ bước routing ở trên).

"THÀNH PHẦN HỒ SƠ" được parse thành dữ liệu có cấu trúc (danh sách "Trường
hợp", mỗi trường hợp là danh sách giấy tờ kèm số lượng) thay vì giữ nguyên
text thô mất định dạng bảng — pypdf làm phẳng bảng PDF thành các dòng tuần
tự không có ranh giới cột, nhưng cột "Số lượng" luôn nhận một trong vài giá
trị cố định (regex _QUANTITY_LINE) nên dùng nó làm mốc kết thúc mỗi hàng.

Chạy: uv run python build_index.py
"""

import json
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader

PDF_DIR = Path("data/pdfs")
INDEX_PATH = Path("data/index.json")
PROCEDURES_DIR = Path("data/procedures")

SECTION_HEADINGS = [
    "TRÌNH TỰ THỰC HIỆN",
    "THÀNH PHẦN HỒ SƠ",
    "CÁCH THỨC THỰC HIỆN",
    "CĂN CỨ PHÁP LÝ",
    "CƠ QUAN THỰC HIỆN",
    "YÊU CẦU, ĐIỀU KIỆN THỰC HIỆN",
    "KẾT QUẢ XỬ LÝ",
    "TỪ KHÓA",
    "MÔ TẢ",
]

_HEADING_PATTERN = re.compile(
    r"^(" + "|".join(re.escape(h) for h in SECTION_HEADINGS) + r")\s*$",
    re.MULTILINE,
)

# Mốc kết thúc một hàng trong bảng "THÀNH PHẦN HỒ SƠ" — cột "Số lượng" của
# dữ liệu dichvucong.gov.vn chỉ nhận vài giá trị cố định này.
_QUANTITY_LINE = re.compile(r"^(\d+\s+bản\s+(chính|sao)|Không\s+có)\s*$", re.IGNORECASE)
_CASE_HEADER = re.compile(r"^Trường hợp\s+\d+\s*:\s*(.*)$")
_TABLE_HEADER_LINE = "Tên giấy tờ Mẫu đơn, tờ khai Số lượng"


def slugify(text: str) -> str:
    # "đ"/"Đ" không có decomposition NFKD về "d" (khác các nguyên âm có
    # dấu) — phải thay tay trước, nếu không ký tự này biến mất khỏi slug.
    text = text.replace("đ", "d").replace("Đ", "D")
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower()
    return ascii_text or "thu-tuc"


def extract_procedure_name(full_text: str) -> str:
    match = re.search(r"Tên thủ tục\s*\n?\s*(.+)", full_text)
    return match.group(1).strip() if match else "Không rõ tên thủ tục"


def extract_procedure_code(full_text: str) -> str | None:
    match = re.search(r"Mã thủ tục\s*\n?\s*([\w.]+)", full_text)
    return match.group(1).strip() if match else None


def split_into_sections(full_text: str) -> list[dict]:
    matches = list(_HEADING_PATTERN.finditer(full_text))
    sections = []

    first_start = matches[0].start() if matches else len(full_text)
    intro = full_text[:first_start].strip()
    if intro:
        sections.append({"title": "THÔNG TIN CHUNG", "content": intro})

    for i, m in enumerate(matches):
        title = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        content = full_text[start:end].strip()
        if content:
            sections.append({"title": title, "content": content})

    return sections


def parse_dossier_section(content: str) -> list[dict]:
    """Parse "THÀNH PHẦN HỒ SƠ" thành list các 'Trường hợp', mỗi trường hợp
    là list giấy tờ {ten_giay_to, so_luong}.

    Chiến lược: quét từng dòng, gom các dòng liên tiếp làm "tên giấy tờ"
    cho tới khi gặp một dòng khớp _QUANTITY_LINE — dòng đó là "số lượng"
    kết thúc hàng hiện tại. Gặp dòng "Trường hợp N: ..." thì mở nhóm mới;
    bỏ qua dòng lặp lại header bảng.

    GIỚI HẠN ĐÃ BIẾT (chấp nhận cho MVP): khi cột "Mẫu đơn, tờ khai" của
    một hàng để trống, pypdf trộn thứ tự text của bảng không nhất quán —
    một số hàng liên tiếp có thể bị ghép lẫn tên giấy tờ với nhau. Ảnh
    hưởng chủ yếu tới các "Trường hợp" chứa nhiều đoạn diễn giải dài (giấy
    tờ xuất trình, lưu ý) — nhóm giấy tờ bắt buộc chính (thường ở "Trường
    hợp 1") ít bị ảnh hưởng vì có ít hàng, câu ngắn hơn. Sửa triệt để cần
    trích bảng theo tọa độ (ví dụ pdfplumber) thay vì text tuần tự — chưa
    làm ở MVP này vì lợi ích không tương xứng effort cho một script chạy
    thủ công, review được bằng mắt trước khi dùng.
    """
    lines = [ln.strip() for ln in content.split("\n") if ln.strip()]
    cases: list[dict] = []
    current_case: dict | None = None
    pending_name_lines: list[str] = []

    def flush_row(quantity: str) -> None:
        nonlocal pending_name_lines
        name = " ".join(pending_name_lines).strip()
        pending_name_lines = []
        if not name or current_case is None:
            return
        current_case["items"].append({"ten_giay_to": name, "so_luong": quantity})

    for line in lines:
        case_match = _CASE_HEADER.match(line)
        if case_match:
            current_case = {"label": case_match.group(1).strip() or line, "items": []}
            cases.append(current_case)
            pending_name_lines = []
            continue
        if line == _TABLE_HEADER_LINE:
            continue
        qty_match = _QUANTITY_LINE.match(line)
        if qty_match:
            flush_row(qty_match.group(0).strip())
            continue
        pending_name_lines.append(line)

    return cases


def _read_source_url(pdf_path: Path) -> str | None:
    """Đọc URL nguồn (nếu có) từ file sidecar '<tên_pdf>.url.txt' cạnh PDF —
    ghi ra lúc upload (xem POST /upload-pdf) khi người dùng dán kèm link
    dichvucong.gov.vn. Không bắt buộc: PDF chép tay/không có link vẫn
    build bình thường, chỉ thiếu source_url."""
    url_path = pdf_path.with_suffix(pdf_path.suffix + ".url.txt")
    if url_path.exists():
        return url_path.read_text(encoding="utf-8").strip() or None
    return None


def build() -> None:
    PROCEDURES_DIR.mkdir(parents=True, exist_ok=True)
    routing_entries = []

    for pdf_path in sorted(PDF_DIR.glob("*.pdf")):
        reader = PdfReader(str(pdf_path))
        full_text = "\n".join(page.extract_text() or "" for page in reader.pages)

        procedure_name = extract_procedure_name(full_text)
        procedure_code = extract_procedure_code(full_text)
        source_url = _read_source_url(pdf_path)
        sections = split_into_sections(full_text)
        slug = slugify(procedure_name)

        detail_sections = []
        for section in sections:
            entry: dict = {"title": section["title"], "content": section["content"]}
            if section["title"] == "THÀNH PHẦN HỒ SƠ":
                entry["dossier_cases"] = parse_dossier_section(section["content"])
            detail_sections.append(entry)

        detail = {
            "procedure_name": procedure_name,
            "procedure_code": procedure_code,
            "source_file": pdf_path.name,
            "source_url": source_url,
            "sections": detail_sections,
        }
        (PROCEDURES_DIR / f"{slug}.json").write_text(
            json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        routing_entries.append(
            {
                "slug": slug,
                "procedure_name": procedure_name,
                "procedure_code": procedure_code,
                "source_file": pdf_path.name,
                "source_url": source_url,
                "section_titles": [s["title"] for s in sections],
            }
        )
        print(f"  {pdf_path.name}: {procedure_name} -> data/procedures/{slug}.json ({len(sections)} section)")

    INDEX_PATH.write_text(
        json.dumps(routing_entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Da ghi {len(routing_entries)} thu tuc vao {INDEX_PATH} (file routing)")


if __name__ == "__main__":
    import sys

    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    PDF_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Dang doc PDF trong {PDF_DIR}/ ...")
    build()
