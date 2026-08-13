"""add smart_det to job

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-13 16:43:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("job", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("smart_det", sa.Boolean(), nullable=True, server_default="1")
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("job", schema=None) as batch_op:
        batch_op.drop_column("smart_det")
