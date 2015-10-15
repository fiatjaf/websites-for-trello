"""new premium_accounts view based on events table

Revision ID: a2088de13a8
Revises: 5a3b95894cc0
Create Date: 2015-10-05 10:19:38.526447

"""

# revision identifiers, used by Alembic.
revision = 'a2088de13a8'
down_revision = '5a3b95894cc0'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute('''
CREATE OR REPLACE VIEW premium_accounts AS 
 SELECT events.user_id,
    (events.data ->> 'enable'::text)::boolean AS premium
   FROM ( SELECT events_1.user_id,
            max(events_1.date) AS last
           FROM events events_1
          WHERE events_1.kind = 'plan'::text AND events_1.data @> '{"plan": "premium"}'::jsonb
          GROUP BY events_1.user_id) me
     JOIN events ON me.user_id::text = events.user_id::text AND me.last = events.date;

CREATE OR REPLACE VIEW custom_domains AS
 SELECT cards."desc" AS domain,
    boards.id AS board_id
   FROM cards
     JOIN lists ON cards.list_id::text = lists.id::text AND lists.name = '_preferences'::text AND cards.name = 'domain'::text
     JOIN boards ON lists.board_id::text = boards.id::text
     JOIN premium_accounts ON boards.user_id::text = premium_accounts.user_id::text
  WHERE premium_accounts.premium AND cards."desc" <> ''::text;
    ''')

    op.drop_column('users', 'premium')

def downgrade():
    op.execute('''
CREATE OR REPLACE VIEW custom_domains AS
 SELECT cards."desc" AS domain,
    boards.id AS board_id
   FROM cards
     JOIN lists ON cards.list_id::text = lists.id::text AND lists.name = '_preferences'::text AND cards.name = 'domain'::text
     JOIN boards ON lists.board_id::text = boards.id::text
     JOIN users ON boards.user_id::text = users.id::text
  WHERE users.premium AND cards."desc" <> ''::text;
    ''')

    op.add_column('users', sa.Column('premium', sa.Boolean(), nullable=True))
