"""Exception của tầng TTS — Mục H của Checklist.

Không đặt trong `app/domain/exceptions.py` vì tầng TTS có I/O (HTTP); domain
(C) phải giữ thuần không phụ thuộc I/O.
"""


class TTSError(Exception):
    """Lớp cha cho mọi lỗi khi gọi TTS."""


class TTSConnectionError(TTSError):
    """Lỗi mạng khi gọi provider."""


class TTSAPIError(TTSError):
    """Provider trả lỗi từ phía API (4xx/5xx)."""


class UnapprovedHostError(TTSError):
    """Hostname cấu hình không nằm trong `approved_ai_hosts` — chặn trước khi gọi (NT-6)."""

    def __init__(self, host: str) -> None:
        self.host = host
        super().__init__(
            f"Host '{host}' không nằm trong danh sách approved_ai_hosts, từ chối gọi."
        )
