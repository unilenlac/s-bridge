"""add algorithm and normalization to job

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-13 11:53:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("job", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("algorithm", sa.String(), nullable=True, server_default="dekker")
        )
        batch_op.add_column(
            sa.Column(
                "normalization", sa.String(), nullable=True, server_default="lemma"
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("job", schema=None) as batch_op:
        batch_op.drop_column("normalization")
        batch_op.drop_column("algorithm")
