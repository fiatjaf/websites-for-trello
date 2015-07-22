"""integer->biginteger

Revision ID: 175c090fade
Revises: 14edc679fb65
Create Date: 2015-07-21 21:47:36.376539

"""

# revision identifiers, used by Alembic.
revision = '175c090fade'
down_revision = '14edc679fb65'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute('''
ALTER TABLE lists
  ALTER COLUMN pos TYPE bigint
    ''')
    op.execute('''
ALTER TABLE cards
  ALTER COLUMN pos TYPE bigint
    ''')

def downgrade():
    pass
