CREATE TABLE users (
    _id character varying(50)
    id character varying(50) PRIMARY KEY,
    email text,
    plan text,
    "paypalProfileId" text,
    registered_on timestamp without time zone,
);

CREATE TABLE boards (
    id character varying(50) PRIMARY KEY,
    user_id character varying(50) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subdomain text UNIQUE NOT NULL,
    name text NOT NULL,
    "desc" text,
    "shortLink" character varying(35) UNIQUE
);

CREATE TABLE lists (
    id character varying(50) PRIMARY KEY,
    slug text NOT NULL,
    board_id character varying(50) NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    name text NOT NULL,
    pos bigint,
    closed boolean,
    visible boolean,
    updated_on timestamp without time zone,
    "pagesList" boolean
);
CREATE INDEX ON lists USING btree ("pagesList");
CREATE INDEX ON lists USING btree (slug);
CREATE INDEX ON lists USING btree (visible);

CREATE TABLE labels (
    id character varying(50) PRIMARY KEY,
    slug text,
    board_id character varying(50) NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    name text,
    color text,
    visible boolean
);
CREATE INDEX ON labels USING btree (slug);
CREATE INDEX ON labels USING btree (visible);

CREATE TABLE cards (
    id character varying(50) PRIMARY KEY,
    "shortLink" character varying(35) UNIQUE NOT NULL,
    slug text NOT NULL,
    list_id character varying(50) NOT NULL REFERENCES lists(id) ON DELETE CASCADE,
    name text NOT NULL,
    "desc" text NOT NULL,
    pos bigint,
    due timestamp without time zone,
    checklists jsonb,
    attachments jsonb,
    visible boolean,
    updated_on timestamp without time zone,
    cover text,
    "pageTitle" text,
    labels text[],
    closed boolean,
    users text[],
    syndicated text[]
);
CREATE INDEX ON cards USING btree (name);
CREATE INDEX ON cards USING btree (slug);
CREATE INDEX ON cards USING btree (visible);

CREATE TABLE comments (
    id character varying(50) PRIMARY KEY,
    card_id character varying(50) NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    updated_on timestamp without time zone,
    author_name text,
    author_url text,
    creator_id character varying(50) NOT NULL,
    raw text,
    source_display text,
    source_url text,
    body text
);
