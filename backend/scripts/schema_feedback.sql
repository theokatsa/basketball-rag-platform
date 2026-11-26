-- Questions asked on the site, and what people said about answers and similar-player lists. Additive.
-- No row names a person: no account and no address. "visitor" is a random number kept by one browser,
-- so answers from one person can be grouped without knowing who it is.
-- "source" comes from ASK_LOG_SOURCE (default 'local'), so a study can be told apart from development.

create table if not exists ask_log (
    id uuid primary key,
    source text not null default 'local',
    visitor uuid,
    question text not null,
    previous text,
    understood text not null default '',
    reader text not null default 'rules',   -- which reader turned the question into a plan
    provider text not null,                 -- calculated, extractive, declined, clarify, or the model's provider
    intent text not null default '',
    plan jsonb not null default '[]'::jsonb,
    answer text not null,
    ms integer not null default 0,
    asked_at timestamptz not null default now()
);
create index if not exists ask_log_time on ask_log (asked_at);

create table if not exists answer_feedback (
    ask_id uuid primary key references ask_log(id) on delete cascade,  -- one verdict per answer, the last one counts
    helpful boolean not null,
    reason text,                            -- wrong_stat, wrong_player, should_decline, wrong_number, other
    comment text,
    created_at timestamptz not null default now()
);

create table if not exists similar_feedback (
    id bigint generated always as identity primary key,
    source text not null default 'local',
    visitor uuid not null,
    player_id bigint not null references players(id),
    other_id bigint not null references players(id),
    kind text not null,                     -- overall, style, production
    variant text not null default 'any',    -- any, younger, better
    rank integer not null,                  -- place of other_id in the list, from 1
    similarity real,
    good boolean not null,
    created_at timestamptz not null default now(),
    unique (visitor, player_id, other_id, kind, variant)
);

-- The blind test of similar players: two lists from two methods, in random order; which is more alike?
create table if not exists similarity_judgments (
    id bigint generated always as identity primary key,
    source text not null default 'local',
    visitor uuid not null,
    player_id bigint not null references players(id),
    left_method text not null,
    right_method text not null,
    left_ids bigint[] not null,
    right_ids bigint[] not null,
    choice text not null check (choice in ('left', 'right', 'same')),
    created_at timestamptz not null default now()
);
create index if not exists similarity_judgments_visitor on similarity_judgments (visitor);

-- Conversations on the Scout page, so a chat survives a refresh. Owned by an account, or by the random
-- number of one browser before signing in (claimed by the account on sign-in). Deleting one deletes its messages.
create table if not exists chat_conversations (
    id uuid primary key,
    user_id bigint references app_users(id) on delete cascade,
    visitor uuid,
    title text not null default '',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (user_id is not null or visitor is not null)
);
create index if not exists chat_conversations_user on chat_conversations (user_id, updated_at desc);
create index if not exists chat_conversations_visitor on chat_conversations (visitor, updated_at desc);
create table if not exists chat_messages (
    id bigint generated always as identity primary key,
    conversation_id uuid not null references chat_conversations(id) on delete cascade,
    question text not null,
    answer jsonb not null,     -- the whole answer as the page showed it
    created_at timestamptz not null default now()
);
create index if not exists chat_messages_conversation on chat_messages (conversation_id, id);
alter table chat_conversations enable row level security;
alter table chat_messages enable row level security;

alter table similarity_judgments enable row level security;
alter table ask_log enable row level security;
alter table answer_feedback enable row level security;
alter table similar_feedback enable row level security;
