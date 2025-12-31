"""Add account lockout columns to users table

Revision ID: 001_add_user_lockout
Revises:
Create Date: 2024-12-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_add_user_lockout'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add failed_login_attempts and locked_until columns to users table."""
    # Add failed_login_attempts column
    op.add_column(
        'users',
        sa.Column(
            'failed_login_attempts',
            sa.Integer(),
            nullable=False,
            server_default='0'
        )
    )

    # Add locked_until column
    op.add_column(
        'users',
        sa.Column(
            'locked_until',
            sa.DateTime(timezone=True),
            nullable=True
        )
    )

    # Remove server_default after adding (optional, keeps schema clean)
    op.alter_column('users', 'failed_login_attempts', server_default=None)


def downgrade() -> None:
    """Remove failed_login_attempts and locked_until columns."""
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_login_attempts')
