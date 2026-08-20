"""add token_comparator to job

Revision ID: 3f5a6b7c8d9e
Revises: 2e4f5a6b7c8d
Create Date: 2026-08-19 16:54:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3f5a6b7c8d9e"
down_revision: Union[str, Sequence[str], None] = "2e4f5a6b7c8d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("job", schema=None) as batch_op:
        batch_op.add_column(sa.Column("token_comparator", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("job", schema=None) as batch_op:
        batch_op.drop_column("token_comparator")
