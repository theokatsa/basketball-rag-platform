export type PlayerDirectoryRow = { player_id: number; nba_player_id: number; full_name: string; is_active: boolean; season: string | null; club: string | null; club_full_name: string | null; club_team_id: number | null; games_played: number | null; minutes: number | null; points: number | null; rebounds: number | null; assists: number | null; steals: number | null; blocks: number | null; turnovers: number | null; field_goal_pct: number | null; three_point_pct: number | null; free_throw_pct: number | null; position: string | null; age: number | null };
export type SeasonStat = { player_id: number; season: string; team_id: number | null; position: string | null; games_played: number; minutes: number; points: number; rebounds: number; assists: number; steals: number; blocks: number; turnovers: number; field_goal_pct: number | null; three_point_pct: number | null; free_throw_pct: number | null; points_percentile: number | null; rebounds_percentile: number | null; assists_percentile: number | null; steals_percentile: number | null; blocks_percentile: number | null; field_goal_percentile: number | null; position_points_percentile: number | null; position_rebounds_percentile: number | null; position_assists_percentile: number | null; position_steals_percentile: number | null; position_blocks_percentile: number | null; position_field_goal_percentile: number | null; points_rank: number | null; rebounds_rank: number | null; assists_rank: number | null; steals_rank: number | null; blocks_rank: number | null; turnovers_rank: number | null; field_goal_rank: number | null; three_point_rank: number | null; free_throw_rank: number | null };
export type PlayerProfile = { position: string | null; age: number | null; height: string | null; weight: string | null };
export type GameLog = { player_id: number; game_id: number | null; oreb: number; dreb: number; pf: number; won: boolean; team_points: number; opponent_points: number; opponent_id: number; season: string; minutes: string; points: number; rebounds: number; assists: number; steals: number; blocks: number; turnovers: number; field_goals_made: number; field_goals_attempted: number; three_pointers_made: number; three_pointers_attempted: number; free_throws_made: number; free_throws_attempted: number; plus_minus: number | null; nba_game_id: string | null; game_date: string | null; opponent: string | null; is_home: boolean | null };
export type ShotRecord = { player_id: number; nba_game_id: string; season: string; period: number; minutes_remaining: number; seconds_remaining: number; action_type: string; shot_type: string; shot_zone_basic: string; shot_zone_area: string; shot_zone_range: string; shot_distance: number; loc_x: number; loc_y: number; shot_made: boolean; game_date: string | null; matchup: string };
export type PlayerRecord = { id: number; nba_player_id: number; full_name: string; first_name: string; last_name: string; is_active: boolean };
export type SimilarPlayerResult = { player_id: number; full_name: string; season: string; source_text: string; similarity: number; age: number | null; position: string | null; is_active: boolean; shared_traits: string[]; archetype: string | null; areas: { label: string; closeness: number }[]; alike: TraitGap[]; apart: TraitGap[] };
export type TraitGap = { label: string; percent: boolean; own: number; other: number; closeness: number };
export type PlayerDetailData = { player: PlayerRecord; profile: PlayerProfile; stats: SeasonStat[]; logs: GameLog[] | null; shots: ShotRecord[] | null; similar: SimilarPlayerResult[] };

/** 'name', 'club' or the key of a statistic in stats.ts */
export type SortKey = string;
export type SortDirection = 'asc' | 'desc';
export type View = 'games' | 'game' | 'login' | 'account' | 'home' | 'players' | 'top' | 'teams' | 'team' | 'scout' | 'explorer' | 'shotlab' | 'young' | 'form' | 'lineup' | 'shortlist' | 'player' | 'compare' | 'report' | 'how' | 'judge';
/** One line of the filter builder: this statistic is at least / at most this value. */
export type FilterRule = { id: number; stat: string; op: 'min' | 'max'; value: number };

export type PlayerTotals = { player_id: number; games_played: number; minutes: number; points: number; rebounds: number; assists: number; steals: number; blocks: number; turnovers: number; field_goals_made: number; field_goals_attempted: number; three_pointers_made: number; three_pointers_attempted: number; free_throws_made: number; free_throws_attempted: number; plus_minus: number; oreb: number; dreb: number; pf: number; double_doubles: number; triple_doubles: number; season_age: number | null; off_rating: number | null; def_rating: number | null; net_rating: number | null; ast_pct: number | null; ast_to: number | null; oreb_pct: number | null; dreb_pct: number | null; efg_pct: number | null; usg_pct: number | null; pace: number | null; pie: number | null; defended_fga: number | null; defended_fg_pct: number | null; defended_fg_diff: number | null };
export type ZoneRow = { zone: string; attempts: number; made: number };
export type PlayerZoneRow = ZoneRow & { player_id: number };
export type TeamZoneRow = ZoneRow & { team_id: number };
export type BestGame = { player_id: number; game_id: string; game_date: string | null; team_id: number; opponent_id: number; opponent: string; is_home: boolean; won: boolean; team_points: number; opponent_points: number; points: number; rebounds: number; assists: number; steals: number; blocks: number; field_goals_made: number; field_goals_attempted: number; game_score: number };

export type FormStat = { now: number; before: number; surprise: number; games: (number | null)[] };
export type FormRow = { player_id: number; games_played: number; last_game: string; stats: Record<string, FormStat> };
export type GameSummary = { game_id: string; game_date: string; season: string; home_id: number; away_id: number; home_points: number; away_points: number; overtime: boolean; best: { player_id: number; points: number; reb: number; ast: number; game_score: number } | null };
export type BoxLine = { minutes: number; points: number; fgm: number; fga: number; tpm: number; tpa: number; ftm: number; fta: number; oreb: number; dreb: number; reb: number; ast: number; stl: number; blk: number; tov: number; pf: number };
export type TeamBox = BoxLine & { nba_team_id: number; opponent_points: number; is_home: boolean; won: boolean; abbreviation: string; full_name: string; game_date: string };
export type PlayerBox = BoxLine & { player_id: number; nba_player_id: number; full_name: string; nba_team_id: number; plus_minus: number; game_score: number };
export type GameShot = { player_id: number; nba_team_id: number; period: number; minutes_remaining: number; seconds_remaining: number; shot_type: string; action_type: string; shot_distance: number; loc_x: number; loc_y: number; shot_made: boolean };
export type GameDetail = { game_id: string; teams: TeamBox[]; players: PlayerBox[]; shots: GameShot[]; periods: { nba_team_id: number; period: number; points: number }[] };
export type TeamSide = { points: number; off_rating: number; possessions: number; fg_pct: number; three_pct: number; ft_pct: number; efg: number; ts: number; tov_pct: number; ft_rate: number; three_rate: number; oreb_pct: number; reb: number; ast: number; stl: number; blk: number; tov: number; tpm: number; tpa: number; pf: number };
export type TeamResult = { game_id: string; date: string; opponent_id: number; home: boolean; won: boolean; points: number; opponent_points: number };
export type TeamSummary = { team_id: number; abbreviation: string; name: string; city: string; nickname: string; founded: number; conference: 'East' | 'West'; wins: number; losses: number; win_pct: number; home: [number, number]; away: [number, number]; last10: [number, number]; close: [number, number]; streak: number; margin: number; pace: number; offense: TeamSide; defense: TeamSide; net_rating: number; results: TeamResult[] };
export type Matchup = { other_id: number; games: number; possessions: number; points: number; fgm: number; fga: number; tpm: number; tpa: number; tov: number; blk: number; per100: number; edge: number; expected: number };
export type Defenders = { baseline: number | null; guarded_by: Matchup[]; guarded: Matchup[] };
export type HeadToHead = { off_player_id: number; def_player_id: number; games: number; seconds: number; possessions: number; points: number; fgm: number; fga: number; tpm: number; tpa: number; ftm: number; fta: number; ast: number; tov: number; blk: number; usual: number };
export type Fit = {
  scores: { overall: number; offense: number; defense: number };
  skills: { key: string; label: string; z: number }[];
  ideal_teammates: { player_id: number; score: number; usage: number; reasons: string[] }[];
  pairs: { other_id: number; nba_team_id: number; games: number; minutes: number; net_rating: number; off_rating: number; def_rating: number }[];
  toughest_defenders: Matchup[]; easiest_defenders: Matchup[]; best_stops: Matchup[]; worst_stops: Matchup[];
  teams: { team_id: number; games: number; points: number; rebounds: number; assists: number; ts: number | null; plus_minus: number; game_score: number }[];
  baseline: number | null;
};
export type LineupResult = {
  offense: number; defense: number; net: number; league: number; total_usage: number; average_height: number | null;
  shares: { player_id: number; own: number; in_lineup: number; points_per_100: number; own_points_per_100: number }[];
  stats: { label: string; own: number; base: number; higher: boolean; note: string; z: number }[];
  checks: { label: string; target: number; players: number[]; note: string }[];
  pairs: { player_a: number; player_b: number; minutes: number; net_rating: number }[];
  opponents: { player_id: number; toughest: { player_id: number; notes: string[] }[]; easiest: { player_id: number; notes: string[] }[] }[];
};
export type PlayerScore = { player_id: number; score: number; offense: number; defense: number };
export type User = { id: number; email: string; display_name: string; created_at: string };
export type UserState = { favorites?: number[]; groups?: Record<string, number[]>; history?: number[]; notes?: Record<number, ScoutNote> };
export type ScoutNote = { text: string; stars: number; status: string };
