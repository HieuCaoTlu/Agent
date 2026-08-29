"""them cot tinh toan duration_ms cho bang sessions

Revision ID: 35ba18f53593
Revises: 4f6a7f86f019
Create Date: 2026-08-30 01:33:58.373316

Ghi chú: `duration_ms` là cột tính toán (GENERATED ALWAYS AS ... STORED) —
Postgres hỗ trợ cú pháp này native (Mục 8.2 của Plan). SQLite không có cột
generated dùng STORED tương đương qua ALTER TABLE, nên khi chạy trên SQLite
(chỉ dùng cho dev/test khi chưa có Postgres — xem README.md) migration này
tạo một cột thường và để ORM/service tự tính lại nếu cần, thay vì để DB
tính. Trên Postgres (production/staging), cột luôn được DB tính tự động.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '35ba18f53593'
down_revision: Union[str, Sequence[str], None] = '4f6a7f86f019'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            ALTER TABLE sessions
            ADD COLUMN duration_ms INTEGER GENERATED ALWAYS AS (
                CASE WHEN completed_at IS NOT NULL
                     THEN CAST(EXTRACT(EPOCH FROM (completed_at - started_at)) * 1000 AS INTEGER)
                     ELSE NULL
                END
            ) STORED
            """
        )
    else:
        # SQLite (dev/test) — cột thường, không tự tính; service tầng trên
        # (SessionService.complete_session) chịu trách nhiệm ghi giá trị này.
        op.add_column("sessions", sa.Column("duration_ms", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("sessions", "duration_ms")
