CREATE OR REPLACE VIEW custom_domains AS
 SELECT cards."desc" AS domain,
    boards.id AS board_id
   FROM cards
     JOIN lists ON cards.list_id::text = lists.id::text AND lists.name = '_preferences'::text AND cards.name = 'domain'::text
     JOIN boards ON lists.board_id::text = boards.id::text
     JOIN users ON boards.user_id::text = users.id::text
  WHERE users.plan = 'premium' AND cards."desc" <> ''::text;

CREATE VIEW prefs_cards AS
 SELECT cards.name,
    cards."desc",
    cards.attachments,
    cards.checklists,
    boards.subdomain,
    custom_domains.domain,
    cards.cover
   FROM (((cards
     JOIN lists ON ((((cards.list_id)::text = (lists.id)::text) AND (lists.name = '_preferences'::text))))
     JOIN boards ON (((lists.board_id)::text = (boards.id)::text)))
     LEFT JOIN custom_domains ON (((custom_domains.board_id)::text = (boards.id)::text)));

