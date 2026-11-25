import type { PlayerDirectoryRow, PlayerTotals } from './types';

export type StatGroup = 'Scoring' | 'Shooting' | 'Playmaking' | 'Rebounding' | 'Defense' | 'Impact' | 'Other';
export type StatDef = {
  key: string; label: string; short: string; group: StatGroup; digits: number; suffix?: string; lowerIsBetter?: boolean; signed?: boolean;
  /** Minimum season attempts for the number to mean something. */
  attempts?: [(t: PlayerTotals) => number, number];
  unit?: string;
  get: (p: PlayerDirectoryRow, t?: PlayerTotals) => number | null;
  /** Season total, when one exists. */
  total?: (t: PlayerTotals) => number | string;
};

type TotalKey = { [K in keyof PlayerTotals]: PlayerTotals[K] extends number ? K : never }[keyof PlayerTotals];
type RateKey = { [K in keyof PlayerTotals]: null extends PlayerTotals[K] ? K : never }[keyof PlayerTotals];
const perGame = (key: 'points' | 'rebounds' | 'assists' | 'steals' | 'blocks' | 'turnovers' | 'minutes') => (p: PlayerDirectoryRow) => p[key];
const each = (key: TotalKey) => (_: PlayerDirectoryRow, t?: PlayerTotals) => (t?.games_played ? t[key] / t.games_played : null);
const rate = (key: RateKey) => (_: PlayerDirectoryRow, t?: PlayerTotals) => t?.[key] ?? null;
const sum = (key: TotalKey) => (t: PlayerTotals) => t[key];
const split = (made: TotalKey, tried: TotalKey) => (t: PlayerTotals) => `${t[made]}/${t[tried]}`;

/** Game Score per game (Hollinger). */
export function production(t?: PlayerTotals): number | null {
  if (!t?.games_played) return null;
  return (t.points + 0.4 * t.field_goals_made - 0.7 * t.field_goals_attempted - 0.4 * (t.free_throws_attempted - t.free_throws_made) + 0.7 * t.oreb + 0.3 * t.dreb + t.steals + 0.7 * t.assists + 0.7 * t.blocks - 0.4 * t.pf - t.turnovers) / t.games_played;
}
const FGA: [(t: PlayerTotals) => number, number] = [(t) => t.field_goals_attempted, 200];
const MINUTES: [(t: PlayerTotals) => number, number] = [(t) => t.minutes, 500];

export const STATS: StatDef[] = [
  { key: 'points', label: 'Points', short: 'PTS', group: 'Scoring', digits: 1, get: perGame('points'), total: sum('points') },
  { key: 'fgm', label: 'Field goals made', short: 'FGM', group: 'Scoring', digits: 1, get: each('field_goals_made'), total: sum('field_goals_made') },
  { key: 'threes', label: 'Threes made', short: '3PM', group: 'Scoring', digits: 1, get: each('three_pointers_made'), total: sum('three_pointers_made') },
  { key: 'ftm', label: 'Free throws made', short: 'FTM', group: 'Scoring', digits: 1, get: each('free_throws_made'), total: sum('free_throws_made') },
  { key: 'fta', label: 'Free throws attempted', short: 'FTA', group: 'Scoring', digits: 1, get: each('free_throws_attempted'), total: sum('free_throws_attempted') },
  { key: 'usage', label: 'Usage rate', short: 'USG%', group: 'Scoring', digits: 1, suffix: '%', attempts: MINUTES, unit: 'minutes', get: rate('usg_pct') },
  { key: 'ts', label: 'True shooting', short: 'TS%', group: 'Shooting', digits: 1, suffix: '%', attempts: FGA, get: (_, t) => { const att = t ? t.field_goals_attempted + 0.44 * t.free_throws_attempted : 0; return t && att ? (t.points / (2 * att)) * 100 : null; } },
  { key: 'efg', label: 'Effective field goal', short: 'eFG%', group: 'Shooting', digits: 1, suffix: '%', attempts: FGA, get: rate('efg_pct') },
  { key: 'fg', label: 'Field goal', short: 'FG%', group: 'Shooting', digits: 1, suffix: '%', attempts: FGA, get: (p) => p.field_goal_pct, total: split('field_goals_made', 'field_goals_attempted') },
  { key: 'three', label: 'Three-point', short: '3P%', group: 'Shooting', digits: 1, suffix: '%', attempts: [(t) => t.three_pointers_attempted, 100], get: (p) => p.three_point_pct, total: split('three_pointers_made', 'three_pointers_attempted') },
  { key: 'ft', label: 'Free throw', short: 'FT%', group: 'Shooting', digits: 1, suffix: '%', attempts: [(t) => t.free_throws_attempted, 75], get: (p) => p.free_throw_pct, total: split('free_throws_made', 'free_throws_attempted') },
  { key: 'assists', label: 'Assists', short: 'AST', group: 'Playmaking', digits: 1, get: perGame('assists'), total: sum('assists') },
  { key: 'ast_pct', label: 'Assist rate', short: 'AST%', group: 'Playmaking', digits: 1, suffix: '%', attempts: MINUTES, unit: 'minutes', get: rate('ast_pct') },
  { key: 'ast_to', label: 'Assists per turnover', short: 'A/TO', group: 'Playmaking', digits: 2, attempts: MINUTES, unit: 'minutes', get: rate('ast_to') },
  { key: 'turnovers', label: 'Turnovers', short: 'TOV', group: 'Playmaking', digits: 1, lowerIsBetter: true, get: perGame('turnovers'), total: sum('turnovers') },
  { key: 'rebounds', label: 'Rebounds', short: 'REB', group: 'Rebounding', digits: 1, get: perGame('rebounds'), total: sum('rebounds') },
  { key: 'oreb', label: 'Offensive rebounds', short: 'OREB', group: 'Rebounding', digits: 1, get: each('oreb'), total: sum('oreb') },
  { key: 'dreb', label: 'Defensive rebounds', short: 'DREB', group: 'Rebounding', digits: 1, get: each('dreb'), total: sum('dreb') },
  { key: 'oreb_pct', label: 'Offensive rebound rate', short: 'OR%', group: 'Rebounding', digits: 1, suffix: '%', attempts: MINUTES, unit: 'minutes', get: rate('oreb_pct') },
  { key: 'dreb_pct', label: 'Defensive rebound rate', short: 'DR%', group: 'Rebounding', digits: 1, suffix: '%', attempts: MINUTES, unit: 'minutes', get: rate('dreb_pct') },
  { key: 'steals', label: 'Steals', short: 'STL', group: 'Defense', digits: 1, get: perGame('steals'), total: sum('steals') },
  { key: 'blocks', label: 'Blocks', short: 'BLK', group: 'Defense', digits: 1, get: perGame('blocks'), total: sum('blocks') },
  { key: 'dfg', label: 'Opponent FG% when guarding', short: 'DFG%', group: 'Defense', digits: 1, suffix: '%', lowerIsBetter: true, attempts: [(t) => t.defended_fga ?? 0, 200], unit: 'shots guarded', get: rate('defended_fg_pct') },
  { key: 'dfg_diff', label: 'Opponent FG% vs their average', short: 'DFG±', group: 'Defense', digits: 1, signed: true, lowerIsBetter: true, attempts: [(t) => t.defended_fga ?? 0, 200], unit: 'shots guarded', get: rate('defended_fg_diff') },
  { key: 'def_rating', label: 'Defensive rating', short: 'DRtg', group: 'Defense', digits: 1, lowerIsBetter: true, attempts: MINUTES, unit: 'minutes', get: rate('def_rating') },
  { key: 'pf', label: 'Fouls', short: 'PF', group: 'Defense', digits: 1, lowerIsBetter: true, get: each('pf'), total: sum('pf') },
  { key: 'production', label: 'Game Score', short: 'GmSc', group: 'Impact', digits: 1, get: (_, t) => production(t) },
  { key: 'plus_minus', label: 'Plus/minus', short: '+/−', group: 'Impact', digits: 1, signed: true, get: each('plus_minus'), total: (t) => (t.plus_minus > 0 ? `+${t.plus_minus}` : t.plus_minus) },
  { key: 'net_rating', label: 'Net rating', short: 'Net', group: 'Impact', digits: 1, signed: true, attempts: MINUTES, unit: 'minutes', get: rate('net_rating') },
  { key: 'off_rating', label: 'Offensive rating', short: 'ORtg', group: 'Impact', digits: 1, attempts: MINUTES, unit: 'minutes', get: rate('off_rating') },
  { key: 'pie', label: 'Player impact estimate', short: 'PIE', group: 'Impact', digits: 1, suffix: '%', attempts: MINUTES, unit: 'minutes', get: rate('pie') },
  { key: 'double_doubles', label: 'Double-doubles', short: 'DD', group: 'Impact', digits: 0, get: (_, t) => t?.double_doubles ?? null, total: sum('double_doubles') },
  { key: 'triple_doubles', label: 'Triple-doubles', short: 'TD', group: 'Impact', digits: 0, get: (_, t) => t?.triple_doubles ?? null, total: sum('triple_doubles') },
  { key: 'games_played', label: 'Games', short: 'GP', group: 'Other', digits: 0, get: (p) => p.games_played, total: sum('games_played') },
  { key: 'minutes', label: 'Minutes', short: 'MIN', group: 'Other', digits: 1, get: perGame('minutes'), total: sum('minutes') },
  { key: 'age', label: 'Age in 2024-25', short: 'AGE', group: 'Other', digits: 0, get: (p, t) => t?.season_age ?? p.age },
];
const index = new Map(STATS.map((s) => [s.key, s]));
export const statByKey = (key: string) => index.get(key) ?? STATS[0];
export const formatStat = (s: StatDef, v: number | null) => (v == null ? '–' : `${s.signed && v > 0 ? '+' : ''}${v.toFixed(s.digits)}${s.suffix ?? ''}`);
export const STAT_GROUPS: StatGroup[] = ['Scoring', 'Shooting', 'Playmaking', 'Rebounding', 'Defense', 'Impact'];
/** Enough attempts (or minutes) for this number to be compared fairly. */
export const qualifies = (s: StatDef, t?: PlayerTotals) => !s.attempts || (t != null && s.attempts[0](t) >= s.attempts[1]);

export const POSITIONS = ['Guard', 'Forward', 'Center'];
export const playsPosition = (p: PlayerDirectoryRow, position: string) => !position || (p.position ?? '').includes(position);

/** Colours for compared players, checked for colour-blind separation on the dark surface. */
export const SERIES = ['#e8590c', '#3987e5', '#199e70', '#9085e9', '#c98500', '#d55181'];
export const MAX_COMPARE = SERIES.length;
