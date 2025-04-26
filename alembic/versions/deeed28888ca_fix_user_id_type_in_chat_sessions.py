"""fix user_id type in chat_sessions

Revision ID: deeed28888ca
Revises: 9a7f6783499b
Create Date: 2025-04-26 09:17:21.112741

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'deeed28888ca'
down_revision: Union[str, None] = '9a7f6783499b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Manually tell Postgres HOW to cast the value
    op.execute('ALTER TABLE chat_sessions ALTER COLUMN user_id TYPE INTEGER USING user_id::integer;')

def downgrade() -> None:
    """Downgrade schema."""
    # Reverse it manually also
    op.execute('ALTER TABLE chat_sessions ALTER COLUMN user_id TYPE UUID USING user_id::uuid;')

