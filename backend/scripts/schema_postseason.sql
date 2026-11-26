-- Play-in and playoff games, kept apart from the regular season so that no query can mix them.
-- The same columns as the regular-season tables, plus season_type ('PlayIn' or 'Playoffs').
-- Filled by: python scripts/ingest_season.py --season <season> --postseason
create table if not exists postseason_player_season_stats (like player_season_stats including defaults);
create table if not exists postseason_player_advanced_stats (like player_advanced_stats including defaults);
create table if not exists postseason_player_box_scores (like player_box_scores including defaults);
create table if not exists postseason_team_box_scores (like team_box_scores including defaults);
create table if not exists postseason_team_period_scores (like team_period_scores including defaults);
create table if not exists postseason_player_matchups (like player_matchups including defaults);
create table if not exists postseason_player_pairs (like player_pairs including defaults);
create table if not exists postseason_shot_charts (like shot_charts including defaults);

alter table postseason_player_season_stats add column if not exists season_type text not null default 'Playoffs';
alter table postseason_player_advanced_stats add column if not exists season_type text not null default 'Playoffs';
alter table postseason_player_box_scores add column if not exists season_type text not null default 'Playoffs';
alter table postseason_team_box_scores add column if not exists season_type text not null default 'Playoffs';
alter table postseason_team_period_scores add column if not exists season_type text not null default 'Playoffs';
alter table postseason_player_matchups add column if not exists season_type text not null default 'Playoffs';
alter table postseason_player_pairs add column if not exists season_type text not null default 'Playoffs';
alter table postseason_shot_charts add column if not exists season_type text not null default 'Playoffs';

create unique index if not exists postseason_player_season_stats_key on postseason_player_season_stats (player_id, season, season_type, team_id);
create unique index if not exists postseason_player_advanced_stats_key on postseason_player_advanced_stats (player_id, season, season_type);
create unique index if not exists postseason_player_box_scores_key on postseason_player_box_scores (nba_game_id, player_id);
create unique index if not exists postseason_team_box_scores_key on postseason_team_box_scores (nba_game_id, nba_team_id);
create unique index if not exists postseason_team_period_scores_key on postseason_team_period_scores (nba_game_id, nba_team_id, period);
create unique index if not exists postseason_player_matchups_key on postseason_player_matchups (season, season_type, off_player_id, def_player_id);
create unique index if not exists postseason_player_pairs_key on postseason_player_pairs (season, season_type, nba_team_id, player_a, player_b);
create unique index if not exists postseason_shot_charts_key on postseason_shot_charts (nba_player_id, nba_game_id, period, minutes_remaining, seconds_remaining, loc_x, loc_y);
create index if not exists postseason_shot_charts_player on postseason_shot_charts (player_id, season);

alter table postseason_player_season_stats enable row level security;
alter table postseason_player_advanced_stats enable row level security;
alter table postseason_player_box_scores enable row level security;
alter table postseason_team_box_scores enable row level security;
alter table postseason_team_period_scores enable row level security;
alter table postseason_player_matchups enable row level security;
alter table postseason_player_pairs enable row level security;
alter table postseason_shot_charts enable row level security;
