"""much better preferences() function with nav

Revision ID: 7c660464f9f
Revises: 1caa6b800107
Create Date: 2015-04-16 17:31:38.929104

"""

# revision identifiers, used by Alembic.
revision = '7c660464f9f'
down_revision = '1caa6b800107'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    op.execute('''
CREATE OR REPLACE VIEW prefs_cards AS

SELECT cards.name,
       cards."desc",
       cards.attachments,
       cards.checklists,
       boards.subdomain,
       custom_domains.domain
FROM cards
JOIN lists ON cards.list_id::text = lists.id::text AND lists.name = '_preferences'::text
JOIN boards ON lists.board_id::text = boards.id::text
LEFT JOIN custom_domains ON custom_domains.board_id::text = boards.id::text;
    ''')

    op.execute('''
CREATE OR REPLACE FUNCTION markdown_link(source text) RETURNS json as $$
DECLARE link json;
BEGIN

SELECT row_to_json(p) INTO link FROM (
  SELECT
    CASE WHEN position('(' in source) = 0 OR position(']' in source) = 0 THEN source
         ELSE split_part(split_part(source, '[', 2), ']', 1)
    END AS text,
    CASE WHEN position('(' in source) = 0 OR position(']' in source) = 0 THEN source
         ELSE lower(split_part(split_part(source, '(', 2), ')', 1))
    END AS url
)p;

RETURN link;
END;
$$  LANGUAGE plpgsql;
    ''')

    op.execute('''
CREATE OR REPLACE FUNCTION preferences(text) RETURNS json as $$
DECLARE prefs json;
BEGIN

WITH pcards AS (
  SELECT * FROM prefs_cards WHERE domain = $1 OR subdomain = $1
), includes AS (
  SELECT attachment->>'url' AS url
  FROM
    (SELECT jsonb_array_elements(pcards.attachments->'attachments') AS attachment
     FROM pcards
     WHERE name = 'includes')t
  UNION SELECT markdown_link(checkitem->>'name')->>'url' AS url
  FROM
    (SELECT jsonb_array_elements(c->'checkItems') AS checkitem
       FROM
         (SELECT jsonb_array_elements(checklists->'checklists') AS c
          FROM pcards
          WHERE name = 'includes')f
    )p
    WHERE checkitem->>'state' = 'complete'
), nav AS (
  SELECT markdown_link(checkitem->>'name') AS url
  FROM
    (SELECT jsonb_array_elements(c->'checkItems') AS checkitem
     FROM
       (SELECT jsonb_array_elements(jsonb_extract_path(checklists, 'checklists')) AS c
        FROM pcards
        WHERE name = 'nav')f
    )p
)

SELECT json_object_agg(key, value) INTO prefs
FROM (
  SELECT key, value::json FROM
      (
         (SELECT 'includes' AS key,
                 to_json(array_agg(url))::text AS value
          FROM includes)
      UNION
         (SELECT 'nav' AS key,
                 to_json(array_agg(url))::text AS value
          FROM nav)
       UNION 
         (SELECT pcards.name AS key,
                 to_json(pcards.desc::text)::text AS value
          FROM pcards
          WHERE length(pcards.desc) < 100
            AND pcards.name NOT IN ('nav', 'includes'))
      )kv
)kvj
;

RETURN prefs;

END;
$$  LANGUAGE plpgsql;
    ''')

def downgrade():
    op.execute('DROP VIEW prefs_cards')
    op.execute('DROP FUNCTION markdown_link')
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
