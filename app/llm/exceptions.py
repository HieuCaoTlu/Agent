"""Exception của tầng LLM — Mục F2 của Checklist.

Không đặt trong `app/domain/exceptions.py` vì tầng LLM có I/O (gọi API mạng);
domain (C) phải giữ thuần không phụ thuộc I/O.
"""


class LLMError(Exception):
    """Lớp cha cho mọi lỗi khi gọi LLM."""


class LLMTimeoutError(LLMError):
    """Lệnh gọi LLM vượt quá thời gian chờ cho phép."""


class LLMRateLimitError(LLMError):
    """Provider từ chối do vượt giới hạn tần suất — có thể retry sau."""


class LLMConnectionError(LLMError):
    """Lỗi mạng (không kết nối được, DNS, TLS...) khi gọi provider."""


class LLMAPIError(LLMError):
    """Provider trả lỗi từ phía API (4xx/5xx không phải rate limit)."""


class UnapprovedHostError(LLMError):
    """Hostname cấu hình không nằm trong `approved_ai_hosts` — chặn trước khi gọi (NT-6)."""

    def __init__(self, host: str) -> None:
        self.host = host
        super().__init__(
            f"Host '{host}' không nằm trong danh sách approved_ai_hosts, từ chối gọi."
        )
