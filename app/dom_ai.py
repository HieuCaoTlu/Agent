from app import text_model

_MAX_HTML_CHARS = 60_000


async def pick_search_result(html: str, procedure_name: str) -> dict:
    schema = {
        "type": "OBJECT",
        "properties": {
            "result_selector": {"type": "STRING", "nullable": True},
        },
        "required": ["result_selector"],
    }
    prompt = (
        "Đây là HTML trang kết quả tìm kiếm thủ tục hành chính trên "
        f"dichvucong.gov.vn. Tìm kết quả khớp với thủ tục có tên "
        f'"{procedure_name}" nhất. Trả về CSS selector duy nhất trỏ vào '
        "phần tử CÓ THỂ BẤM (link/nút) để mở trang chi tiết của kết quả đó "
        "(document.querySelector() phải chọn đúng 1 phần tử). Nếu không có "
        f"kết quả nào phù hợp, trả null.\n\nHTML:\n{html[:_MAX_HTML_CHARS]}"
    )
    return await text_model.generate_json(prompt, schema)
