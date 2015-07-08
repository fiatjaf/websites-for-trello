"""view and stored procedures for preferences fetching

Revision ID: 2c8e58c14c4c
Revises: 181a9a17af6e
Create Date: 2015-03-25 22:50:55.959397

"""

# revision identifiers, used by Alembic.
revision = '2c8e58c14c4c'
down_revision = '181a9a17af6e'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute('''
CREATE VIEW custom_domains AS
   SELECT cards.desc AS domain,
           boards.id AS board_id
   FROM cards
   INNER JOIN lists ON cards.list_id = lists.id
   AND lists.name = '_preferences'
   AND cards.name = 'domain'
   INNER JOIN boards ON lists.board_id = boards.id
   INNER JOIN users ON boards.user_id = users.id
   WHERE users.custom_domain_enabled
    ''')
    op.execute('''
CREATE OR REPLACE FUNCTION preferences(text) RETURNS json as $$
DECLARE prefs json;
BEGIN

WITH prefs_cards AS
  ( SELECT cards.name,
           cards.desc,
           cards.attachments,
           cards.checklists
   FROM cards
   INNER JOIN lists ON cards.list_id = lists.id
   AND lists.name = '_preferences'
   INNER JOIN boards ON lists.board_id = boards.id
   LEFT OUTER JOIN custom_domains ON custom_domains.board_id = boards.id
   WHERE boards.subdomain = $1
     OR custom_domains.domain = $1),
     includes AS
  ( SELECT attachment->>'url' AS url
   FROM
     (SELECT jsonb_array_elements(jsonb_extract_path(prefs_cards.attachments, 'attachments')) AS attachment
      FROM prefs_cards
      WHERE name = 'includes' ) AS t
   UNION SELECT checkitem->>'name' AS url
   FROM
     (SELECT jsonb_array_elements(c->'checkItems') AS checkitem
      FROM
        (SELECT jsonb_array_elements(jsonb_extract_path(checklists, 'checklists')) AS c
         FROM prefs_cards
         WHERE name = 'includes' ) AS f) AS p
   WHERE checkitem->>'state' = 'complete')
SELECT json_object_agg(key, value) INTO prefs
FROM
  (
     (SELECT 'includes' AS key,
             string_agg(url, ',') AS value
      FROM includes)
   UNION 
     (SELECT prefs_cards.name AS key,
             prefs_cards.desc AS value
      FROM prefs_cards
      WHERE length(prefs_cards.desc) < 100)
  ) AS keyvalues
;

RETURN prefs;

END;
$$  LANGUAGE plpgsql;
    ''')

def downgrade():
    op.execute('DROP VIEW custom_domains;')
    op.execute('DROP FUNCTION preferences(text);')
