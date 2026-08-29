"""Exception của tầng STT — Mục G của Checklist.

Không đặt trong `app/domain/exceptions.py` vì tầng STT có I/O (WebSocket/HTTP);
domain (C) phải giữ thuần không phụ thuộc I/O.
"""


class STTError(Exception):
    """Lớp cha cho mọi lỗi khi gọi STT."""


class STTConnectionError(STTError):
    """Lỗi mạng/WebSocket khi gọi provider — audio đã trôi qua, không retry vô hạn (G4)."""


class STTAPIError(STTError):
    """Provider trả lỗi từ phía API (4xx/5xx, hoặc message lỗi qua WebSocket)."""


class UnapprovedHostError(STTError):
    """Hostname cấu hình không nằm trong `approved_ai_hosts` — chặn trước khi gọi (NT-6)."""

    def __init__(self, host: str) -> None:
        self.host = host
        super().__init__(
            f"Host '{host}' không nằm trong danh sách approved_ai_hosts, từ chối gọi."
        )
