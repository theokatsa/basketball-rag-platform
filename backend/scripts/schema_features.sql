-- Additive tables for game history, advanced stats, matchups and user accounts.
-- Row level security is on with no policies: the Supabase REST API cannot read these
-- tables, only the backend's own database connection can.

create table if not exists team_box_scores (
    nba_game_id text not null,
    season text not null,
    game_date date not null,
    nba_team_id integer not null,
    opponent_nba_team_id integer not null,
    is_home boolean not null,
    won boolean not null,
    points integer not null, opponent_points integer not null,
    fgm integer not null, fga integer not null, tpm integer not null, tpa integer not null,
    ftm integer not null, fta integer not null, oreb integer not null, dreb integer not null,
    reb integer not null, ast integer not null, stl integer not null, blk integer not null,
    tov integer not null, pf integer not null, minutes integer not null,
    primary key (nba_game_id, nba_team_id)
);

create table if not exists team_period_scores (
    nba_game_id text not null,
    nba_team_id integer not null,
    season text not null,
    period integer not null,
    points integer not null, fgm integer not null, fga integer not null, tpm integer not null, tpa integer not null,
    ftm integer not null, fta integer not null, reb integer not null, ast integer not null, tov integer not null,
    primary key (nba_game_id, nba_team_id, period)
);

create table if not exists player_box_scores (
    nba_game_id text not null,
    player_id bigint not null references players(id),
    season text not null,
    game_date date not null,
    nba_team_id integer not null,
    minutes integer not null,
    points integer not null, fgm integer not null, fga integer not null, tpm integer not null, tpa integer not null,
    ftm integer not null, fta integer not null, oreb integer not null, dreb integer not null,
    reb integer not null, ast integer not null, stl integer not null, blk integer not null,
    tov integer not null, pf integer not null, plus_minus integer not null,
    primary key (nba_game_id, player_id)
);
create index if not exists player_box_scores_player on player_box_scores (player_id, game_date);

create table if not exists player_advanced_stats (
    player_id bigint not null references players(id),
    season text not null,
    season_age integer,
    off_rating real, def_rating real, net_rating real,
    ast_pct real, ast_to real, oreb_pct real, dreb_pct real, reb_pct real,
    tov_pct real, efg_pct real, ts_pct real, usg_pct real, pace real, pie real, possessions integer,
    defended_fga real, defended_fg_pct real, defended_fg_diff real,
    primary key (player_id, season)
);

create table if not exists player_matchups (
    season text not null,
    off_player_id bigint not null references players(id),
    def_player_id bigint not null references players(id),
    games integer not null, seconds integer not null, possessions real not null,
    points real not null, team_points real not null, ast real not null, tov real not null, blk real not null,
    fgm real not null, fga real not null, tpm real not null, tpa real not null, ftm real not null, fta real not null,
    primary key (season, off_player_id, def_player_id)
);
create index if not exists player_matchups_def on player_matchups (season, def_player_id);

create table if not exists player_pairs (
    season text not null,
    nba_team_id integer not null,
    player_a bigint not null references players(id),
    player_b bigint not null references players(id),
    games integer not null, minutes real not null, possessions integer,
    off_rating real, def_rating real, net_rating real,
    primary key (season, nba_team_id, player_a, player_b)
);

create table if not exists app_users (
    id bigint generated always as identity primary key,
    email text not null unique,
    display_name text not null,
    password_hash text not null,
    state jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);
create table if not exists app_sessions (
    token_hash text primary key,
    user_id bigint not null references app_users(id) on delete cascade,
    expires_at timestamptz not null
);
create table if not exists player_views (
    id bigint generated always as identity primary key,
    user_id bigint not null references app_users(id) on delete cascade,
    player_id bigint not null references players(id),
    visit integer not null,
    viewed_at timestamptz not null default now()
);
create index if not exists player_views_player on player_views (player_id);
create index if not exists player_views_user on player_views (user_id, viewed_at);

alter table team_box_scores enable row level security;
alter table team_period_scores enable row level security;
alter table player_box_scores enable row level security;
alter table player_advanced_stats enable row level security;
alter table player_matchups enable row level security;
alter table player_pairs enable row level security;
alter table app_users enable row level security;
alter table app_sessions enable row level security;
alter table player_views enable row level security;
