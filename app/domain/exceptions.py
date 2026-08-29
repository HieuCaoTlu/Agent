"""Exception domain dùng chung — không phụ thuộc I/O.

Đặt ở đây (thay vì rải trong từng module) để tầng API (app/main.py) và tầng domain
(state machine, catalog service...) cùng import được một nguồn duy nhất.
"""


class DomainError(Exception):
    """Lớp cha cho mọi lỗi nghiệp vụ (domain) của hệ thống."""


class InvalidTransitionError(DomainError):
    """Ném ra khi có yêu cầu chuyển trạng thái phiên không hợp lệ.

    Thông báo phải bằng tiếng Việt rõ ràng, vì lỗi này hiển thị trực tiếp cho cán bộ.
    """

    def __init__(self, current_state: str, event: str, message: str | None = None) -> None:
        self.current_state = current_state
        self.event = event
        self.message = message or (
            f"Không thể thực hiện thao tác này ở trạng thái hiện tại của phiên "
            f"(trạng thái: {current_state}, sự kiện: {event})."
        )
        super().__init__(self.message)


class ProcedureNotFound(DomainError):
    """Ném ra khi không tìm thấy thủ tục hành chính theo mã, hoặc thủ tục đã hết hiệu lực."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        self.message = message or f"Không tìm thấy thủ tục hành chính có mã '{code}' đang hiệu lực."
        super().__init__(self.message)
