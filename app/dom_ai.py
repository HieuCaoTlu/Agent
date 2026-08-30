import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

TEXT_MODEL = "gemini-2.5-flash"

_MAX_HTML_CHARS = 60_000

_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


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
    response = await _client.aio.models.generate_content(
        model=TEXT_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema),
    )
    return json.loads(response.text)
