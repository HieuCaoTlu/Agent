"""revoke update delete tren audit_log va field_history

Revision ID: 316bd3fe7369
Revises: 35ba18f53593
Create Date: 2026-08-30 01:34:17.520095

Ghi chú: chỉ áp dụng trên Postgres. SQLite không có mô hình quyền theo role
(GRANT/REVOKE) như Postgres, nên khi chạy trên SQLite (dev/test) migration
này là no-op — tính bất biến của audit_log/field_history ở môi trường dev chỉ
được đảm bảo ở tầng ứng dụng (repository không có hàm update/delete — xem
Checklist.MD mục B4: FieldHistoryRepository/AuditRepository chỉ có append).

Role `app_user` phải khớp với user trong DATABASE_URL (xem .env.example).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '316bd3fe7369'
down_revision: Union[str, Sequence[str], None] = '35ba18f53593'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("REVOKE UPDATE, DELETE ON audit_log FROM app_user")
        op.execute("REVOKE UPDATE, DELETE ON field_history FROM app_user")


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("GRANT UPDATE, DELETE ON audit_log TO app_user")
        op.execute("GRANT UPDATE, DELETE ON field_history TO app_user")
