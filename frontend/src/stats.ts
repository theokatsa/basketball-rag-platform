import type { PlayerDirectoryRow, PlayerTotals } from './types';

export type StatDef = { key: string; label: string; short: string; digits: number; suffix?: string; lowerIsBetter?: boolean; /** Minimum season attempts for the number to mean something. */ attempts?: [(t: PlayerTotals) => number, number]; get: (p: PlayerDirectoryRow, t?: PlayerTotals) => number | null };

const perGame = (key: 'points' | 'rebounds' | 'assists' | 'steals' | 'blocks' | 'turnovers' | 'minutes') => (p: PlayerDirectoryRow) => p[key];

/** Game Score per game (Hollinger, with rebounds at 0.45 because splits are not stored). */
export function production(t?: PlayerTotals): number | null {
  if (!t?.games_played) return null;
  return (t.points + 0.4 * t.field_goals_made - 0.7 * t.field_goals_attempted - 0.4 * (t.free_throws_attempted - t.free_throws_made) + 0.45 * t.rebounds + t.steals + 0.7 * t.assists + 0.7 * t.blocks - t.turnovers) / t.games_played;
}

export const STATS: StatDef[] = [
  { key: 'points', label: 'Points', short: 'PTS', digits: 1, get: perGame('points') },
  { key: 'rebounds', label: 'Rebounds', short: 'REB', digits: 1, get: perGame('rebounds') },
  { key: 'assists', label: 'Assists', short: 'AST', digits: 1, get: perGame('assists') },
  { key: 'steals', label: 'Steals', short: 'STL', digits: 1, get: perGame('steals') },
  { key: 'blocks', label: 'Blocks', short: 'BLK', digits: 1, get: perGame('blocks') },
  { key: 'production', label: 'Game Score', short: 'GmSc', digits: 1, get: (_, t) => production(t) },
  { key: 'plus_minus', label: 'Plus/minus', short: '+/−', digits: 1, get: (_, t) => (t?.games_played ? t.plus_minus / t.games_played : null) },
  { key: 'ts', label: 'True shooting', short: 'TS%', digits: 1, suffix: '%', attempts: [(t) => t.field_goals_attempted, 200], get: (_, t) => { const att = t ? t.field_goals_attempted + 0.44 * t.free_throws_attempted : 0; return t && att ? (t.points / (2 * att)) * 100 : null; } },
  { key: 'fg', label: 'Field goal', short: 'FG%', digits: 1, suffix: '%', attempts: [(t) => t.field_goals_attempted, 200], get: (p) => p.field_goal_pct },
  { key: 'three', label: 'Three-point', short: '3P%', digits: 1, suffix: '%', attempts: [(t) => t.three_pointers_attempted, 100], get: (p) => p.three_point_pct },
  { key: 'ft', label: 'Free throw', short: 'FT%', digits: 1, suffix: '%', attempts: [(t) => t.free_throws_attempted, 75], get: (p) => p.free_throw_pct },
  { key: 'threes', label: 'Threes made', short: '3PM', digits: 1, get: (_, t) => (t?.games_played ? t.three_pointers_made / t.games_played : null) },
  { key: 'minutes', label: 'Minutes', short: 'MIN', digits: 1, get: perGame('minutes') },
  { key: 'turnovers', label: 'Turnovers', short: 'TOV', digits: 1, lowerIsBetter: true, get: perGame('turnovers') },
  { key: 'age', label: 'Age', short: 'AGE', digits: 0, get: (p) => p.age },
];
export const statByKey = (key: string) => STATS.find((s) => s.key === key) ?? STATS[0];
export const formatStat = (s: StatDef, v: number | null) => (v == null ? '–' : `${s.key === 'plus_minus' && v > 0 ? '+' : ''}${v.toFixed(s.digits)}${s.suffix ?? ''}`);

export const POSITIONS = ['Guard', 'Forward', 'Center'];
export const playsPosition = (p: PlayerDirectoryRow, position: string) => !position || (p.position ?? '').includes(position);
