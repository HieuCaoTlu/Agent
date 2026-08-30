from app import text_model

_MAX_HTML_CHARS = 60_000


async def analyze_form(html: str, combobox_options: list[dict] | None = None) -> dict:
    schema = {
        "type": "OBJECT",
        "properties": {
            "fields": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "label": {"type": "STRING"},
                        "selector": {"type": "STRING"},
                        "field_type": {"type": "STRING"},
                        "current_value": {"type": "STRING", "nullable": True},
                        "options": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"},
                            "nullable": True,
                        },
                    },
                    "required": ["label", "selector", "field_type"],
                },
            },
        },
        "required": ["fields"],
    }
    combobox_text = ""
    if combobox_options:
        lines = "\n".join(
            f'- selector="{c["selector"]}": {", ".join(c["options"])}' for c in combobox_options
        )
        combobox_text = (
            "\n\nDưới đây là danh sách lựa chọn THẬT đã lấy sẵn cho các ô combobox trên "
            f"trang này (bằng cách bấm mở từng ô), khớp theo selector attribute "
            f"data-scan-field-id có trong HTML:\n{lines}\n\nVới field nào trùng đúng "
            "selector này, PHẢI dùng chính xác selector đó, field_type là \"combobox\", "
            "và điền field \"options\" bằng đúng danh sách lựa chọn thật ở trên (không "
            "tự bịa thêm lựa chọn khác)."
        )
    prompt = (
        "Đây là HTML trang form nộp hồ sơ hành chính trên dichvucong.gov.vn. "
        "Hãy liệt kê TẤT CẢ các trường nhập liệu mà người dùng cần điền (input "
        "text/số/ngày, textarea, ô chọn dạng combobox, radio button, checkbox). "
        "Với mỗi trường trả về: label (tên trường, đọc từ nhãn/placeholder gần "
        "nhất), selector (CSS selector duy nhất trỏ đúng 1 phần tử — "
        "document.querySelector() phải chọn đúng phần tử đó; nếu phần tử có "
        "attribute data-scan-field-id thì PHẢI dùng selector dạng "
        "[data-scan-field-id=\"...\"] đó), field_type (một trong 3 giá trị "
        "chính xác sau — \"text\": input/textarea gõ chữ trực tiếp; "
        "\"combobox\": ô bấm mở ra 1 danh sách lựa chọn ẩn rồi mới chọn (ví dụ "
        "nút có class chứa 'custom-input-typography'); \"choice_option\": MỘT "
        "lựa chọn cụ thể trong nhóm radio button/checkbox đã HIỂN THỊ SẴN "
        "trên trang (ví dụ thẻ tùy chỉnh <x-radio>, <x-checkbox>, hoặc input "
        "type=\"radio\"/\"checkbox\") — với loại này, selector PHẢI trỏ thẳng "
        "vào phần tử CÓ THỂ BẤM của ĐÚNG 1 lựa chọn đó (không phải cả nhóm), "
        "và label PHẢI viết theo dạng \"<tên nhóm câu hỏi>: <tên lựa chọn cụ "
        "thể>\" (ví dụ \"Nơi cư trú: Trong nước\") — nếu 1 nhóm radio có 3 lựa "
        "chọn thì phải trả về 3 field \"choice_option\" riêng biệt, mỗi field "
        "1 selector khác nhau. current_value (giá trị hiện đang có trong "
        "trường, nếu có — với choice_option: true nếu lựa chọn đó đang được "
        "chọn sẵn). options chỉ dùng cho field_type \"combobox\" (xem phần dữ "
        "liệu thật bên dưới), bỏ trống với các loại khác. Bỏ qua các nút bấm "
        "hành động (Nộp hồ sơ, Đồng ý...)."
        f"{combobox_text}\n\nHTML:\n{html[:_MAX_HTML_CHARS]}"
    )
    return await text_model.generate_json(prompt, schema)


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
