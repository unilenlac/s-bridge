"""add current_ref to job

Revision ID: a1b2c3d4e5f6
Revises: 8b244e131ae5
Create Date: 2026-08-12 15:55:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "8b244e131ae5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("job", schema=None) as batch_op:
        batch_op.add_column(sa.Column("current_ref", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("job", schema=None) as batch_op:
        batch_op.drop_column("current_ref")
