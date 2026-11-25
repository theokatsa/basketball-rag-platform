-- Vector store for the RAG pipeline. Additive: no existing table is changed.
create extension if not exists vector;

-- One row per piece of evidence. The same row is searchable by meaning (embedding),
-- by words (tsv) and by facts (kind, player_ids, team_ids, meta).
create table if not exists rag_documents (
    id bigint generated always as identity primary key,
    doc_key text not null unique,          -- "shot_profile:player:123:2024-25"
    kind text not null,                    -- player_season, shot_profile, team_season, ...
    entity text not null,                  -- "player:123", "team:1610612738", "game:0022400061"
    season text not null,
    title text not null,
    content text not null,
    search_text text not null,             -- accent-free copy, so "Jokic" matches "Jokić"
    player_ids bigint[] not null default '{}',
    team_ids integer[] not null default '{}',   -- NBA team ids
    meta jsonb not null default '{}'::jsonb,    -- numbers used for exact filters and rankings
    content_hash text not null,            -- unchanged rows are not embedded again
    embedding vector(384) not null,
    tsv tsvector generated always as (to_tsvector('english', search_text)) stored,
    updated_at timestamptz not null default now()
);
create index if not exists rag_documents_hnsw on rag_documents using hnsw (embedding vector_cosine_ops) with (m = 16, ef_construction = 64);
create index if not exists rag_documents_tsv on rag_documents using gin (tsv);
create index if not exists rag_documents_players on rag_documents using gin (player_ids);
create index if not exists rag_documents_teams on rag_documents using gin (team_ids);
create index if not exists rag_documents_kind on rag_documents (kind, season);

-- Statistical fingerprint of a player-season: twelve z-scores. A separate vector space from
-- the text embeddings, because "plays like" is a question about numbers, not wording.
create table if not exists player_stat_vectors (
    player_id bigint not null references players(id),
    season text not null,
    qualified boolean not null,            -- enough games and minutes to be suggested
    z vector(12) not null,
    updated_at timestamptz not null default now(),
    primary key (player_id, season)
);
create index if not exists player_stat_vectors_hnsw on player_stat_vectors using hnsw (z vector_l2_ops);

alter table rag_documents enable row level security;
alter table player_stat_vectors enable row level security;

-- Learned description of how a player plays (see app/services/style_model.py). features holds the
-- inputs, so that a match can be explained.
create table if not exists player_style_vectors (
    player_id bigint not null references players(id),
    season text not null,
    qualified boolean not null,
    features jsonb not null,
    overall vector(24) not null,
    style vector(24) not null,
    archetype text,
    updated_at timestamptz not null default now(),
    primary key (player_id, season)
);
create index if not exists player_style_vectors_overall on player_style_vectors using hnsw (overall vector_l2_ops);
create index if not exists player_style_vectors_style on player_style_vectors using hnsw (style vector_l2_ops);
alter table player_style_vectors enable row level security;

-- Which embedding model the stored vectors came from: a question must use the same one.
create table if not exists rag_index_info (
    id integer primary key check (id = 1),
    embedding_model text not null,
    built_at timestamptz not null default now()
);
alter table rag_index_info enable row level security;
