"""add joined and transpositions to job

Revision ID: 2e4f5a6b7c8d
Revises: 1d3bad039d50
Create Date: 2026-08-19 14:14:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2e4f5a6b7c8d"
down_revision: Union[str, Sequence[str], None] = "c6c57c77902b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("job", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "joined", sa.Boolean(), nullable=True, server_default=sa.text("1")
            )
        )
        batch_op.add_column(
            sa.Column(
                "transpositions",
                sa.Boolean(),
                nullable=True,
                server_default=sa.text("1"),
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("job", schema=None) as batch_op:
        batch_op.drop_column("transpositions")
        batch_op.drop_column("joined")
