CREATE FUNCTION hex_to_int(hexval character varying) RETURNS integer
    LANGUAGE plpgsql IMMUTABLE STRICT
    AS $$
DECLARE
    result  int;
BEGIN
    EXECUTE 'SELECT x''' || hexval || '''::int' INTO result;
    RETURN result;
END;
$$;

CREATE FUNCTION markdown_link(source text) RETURNS json
    LANGUAGE plpgsql
    AS $$
DECLARE link json;
BEGIN

SELECT row_to_json(p) INTO link FROM (
  SELECT
    CASE WHEN position('(' in source) = 0 OR position(']' in source) = 0 THEN source
         ELSE split_part(split_part(source, '[', 2), ']', 1)
    END AS text,
    CASE WHEN position('(' in source) = 0 OR position(']' in source) = 0 THEN source
         ELSE split_part(split_part(source, '(', 2), ')', 1)
    END AS url
)p;

RETURN link;
END;
$$;

CREATE FUNCTION preferences(text) RETURNS json
    LANGUAGE plpgsql
    AS $_$
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
), comments AS (
  SELECT
    json_object_agg(checkitem->>'name', checkitem->>'state' = 'complete') AS opts
  FROM
    (SELECT jsonb_array_elements(c->'checkItems') AS checkitem
     FROM
      (SELECT jsonb_array_elements(jsonb_extract_path(checklists, 'checklists')) AS c
       FROM pcards
       WHERE name = 'comments')f
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
        (SELECT 'comments' AS key,
                opts::text AS value
        FROM comments)
      UNION 
         (SELECT 'header' AS key,
                 row_to_json(h)::text AS value
          FROM (SELECT "desc" AS text, cover AS image FROM pcards WHERE name = 'header')h)
      UNION 
         (SELECT pcards.name AS key,
                 to_json(pcards.desc::text)::text AS value
          FROM pcards
          WHERE pcards.name IN ('posts-per-page', 'favicon', 'excerpts', 'aside', 'domain'))
      )kv
)kvj
;

RETURN prefs;

END;
$_$;
