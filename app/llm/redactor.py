"""`PIIRedactor` — Mục F4 của Checklist, Mục 10.7 của Plan.

Che dữ liệu nhạy cảm trong transcript trước khi gửi ra dịch vụ bên ngoài
(NT-6). Bản này chỉ che số CCCD (12 chữ số, dạng số hoặc dạng chữ) — theo
đúng phạm vi Mục 10.7 đã nêu; việc có che thêm họ tên/địa chỉ hay không còn
"cần quyết định" (Mục 20 của Plan), nên MVP chỉ làm phần đã được xác nhận rõ.

Bảng ánh xạ placeholder → giá trị thật chỉ giữ trong bộ nhớ của phiên (đối
tượng `PIIRedactor` sống theo phiên), TUYỆT ĐỐI không ghi xuống DB.
"""

import re

_DIGIT_CCCD_PATTERN = re.compile(r"(?<!\d)\d{12}(?!\d)")

_VIETNAMESE_DIGIT_WORDS = {
    "không": "0",
    "một": "1",
    "hai": "2",
    "ba": "3",
    "bốn": "4",
    "tư": "4",
    "năm": "5",
    "lăm": "5",
    "sáu": "6",
    "bảy": "7",
    "tám": "8",
    "chín": "9",
}

# 12 từ chỉ chữ số tiếng Việt liên tiếp, cách nhau bởi khoảng trắng.
_WORD_DIGIT_UNIT = r"(?:" + "|".join(_VIETNAMESE_DIGIT_WORDS) + r")"
_SPOKEN_CCCD_PATTERN = re.compile(
    r"(?<!\S)" + r"(?:" + _WORD_DIGIT_UNIT + r"\s+){11}" + _WORD_DIGIT_UNIT + r"(?!\S)",
    re.IGNORECASE,
)


class PIIRedactor:
    """Che số CCCD trong transcript, giữ bảng ánh xạ trong RAM để khôi phục sau."""

    def __init__(self) -> None:
        self._placeholder_to_value: dict[str, str] = {}
        self._next_index = 1

    def redact(self, transcript: str) -> str:
        """Thay mọi số CCCD (dạng số hoặc dạng chữ) trong `transcript` bằng placeholder."""
        text = _DIGIT_CCCD_PATTERN.sub(self._replace_with_placeholder, transcript)
        text = _SPOKEN_CCCD_PATTERN.sub(self._replace_spoken_with_placeholder, text)
        return text

    def restore(self, text: str) -> str:
        """Thay mọi placeholder `[CCCD_n]` trong `text` (kết quả LLM) về giá trị thật."""
        for placeholder, value in self._placeholder_to_value.items():
            text = text.replace(placeholder, value)
        return text

    def _replace_with_placeholder(self, match: re.Match[str]) -> str:
        return self._register(match.group(0))

    def _replace_spoken_with_placeholder(self, match: re.Match[str]) -> str:
        digits = "".join(_VIETNAMESE_DIGIT_WORDS[w.lower()] for w in match.group(0).split())
        return self._register(digits)

    def _register(self, value: str) -> str:
        placeholder = f"[CCCD_{self._next_index}]"
        self._placeholder_to_value[placeholder] = value
        self._next_index += 1
        return placeholder
