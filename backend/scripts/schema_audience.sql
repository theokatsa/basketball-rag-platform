-- What people look at. Additive, apart from one new column that defaults to false.
alter table app_users add column if not exists is_simulated boolean not null default false;
create index if not exists player_views_time on player_views (viewed_at);

-- "Users also viewed", learned by training/train_also_viewed.py.
create table if not exists player_also_viewed (
    player_id bigint not null references players(id),
    other_id bigint not null references players(id),
    rank integer not null,
    score real not null,
    viewers integer not null,    -- users who opened both in one visit
    audience integer not null,   -- users who opened player_id
    trained_at timestamptz not null default now(),
    primary key (player_id, other_id)
);
alter table player_also_viewed enable row level security;

-- Which players the audience of a player goes on to open, beyond one visit; used for suggestions.
create table if not exists player_audience_links (
    player_id bigint not null references players(id),
    other_id bigint not null references players(id),
    weight real not null,
    primary key (player_id, other_id)
);
alter table player_audience_links enable row level security;
