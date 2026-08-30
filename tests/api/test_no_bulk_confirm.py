"""Mục P — test bảo vệ nguyên tắc lõi NT-1/NT-3: AI hỗ trợ, không thay thế
công chức; cán bộ phải xác nhận từng trường một, không có lối tắt xác nhận
hàng loạt. Xem `app/api/routers/fields.py` (J5)."""

from httpx import AsyncClient


async def test_no_bulk_confirm_endpoint_exists(client: AsyncClient) -> None:
    """Không có endpoint nào (dù đường dẫn hay tên nào) cho phép xác nhận
    nhiều/tất cả trường trong một lời gọi — chỉ có `POST .../fields/{field_name}/confirm`
    (từng trường một, xem J5)."""
    session_resp = await client.post("/api/v1/sessions", json={"staff_name": "Cán bộ A"})
    session_id = session_resp.json()["id"]

    candidate_paths = [
        f"/api/v1/sessions/{session_id}/fields/confirm",
        f"/api/v1/sessions/{session_id}/fields/confirm-all",
        f"/api/v1/sessions/{session_id}/fields/bulk-confirm",
        f"/api/v1/sessions/{session_id}/fields/confirm_all",
    ]
    for path in candidate_paths:
        response = await client.post(path, json={})
        assert response.status_code in (404, 405), (
            f"Endpoint bulk-confirm bất ngờ tồn tại tại {path}: {response.status_code}"
        )
