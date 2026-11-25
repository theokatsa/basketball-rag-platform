import type { GameLog } from '../types';

/** A statistic that can be read from a single game and averaged over many. */
export type LogStat = { key: string; label: string; digits: number; suffix?: string; signed?: boolean; value: (l: GameLog) => number | null; average: (logs: GameLog[]) => number | null; text: (v: number) => string };

const total = (logs: GameLog[], pick: (l: GameLog) => number) => logs.reduce((s, l) => s + pick(l), 0);
const gameScore = (l: GameLog) => l.points + 0.4 * l.field_goals_made - 0.7 * l.field_goals_attempted - 0.4 * (l.free_throws_attempted - l.free_throws_made) + 0.7 * l.oreb + 0.3 * l.dreb + l.steals + 0.7 * l.assists + 0.7 * l.blocks - 0.4 * l.pf - l.turnovers;

function stat(key: string, label: string, pick: (l: GameLog) => number, options: { digits?: number; signed?: boolean } = {}): LogStat {
  const { digits = 0, signed } = options;
  return { key, label, digits, signed, value: pick, average: (logs) => (logs.length ? total(logs, pick) / logs.length : null), text: (v) => `${signed && v > 0 ? '+' : ''}${v.toFixed(1)}` };
}
/** Percentages are averaged by attempts, never as an average of percentages. */
function share(key: string, label: string, made: (l: GameLog) => number, tried: (l: GameLog) => number, scale = 100): LogStat {
  const of = (logs: GameLog[]) => { const att = total(logs, tried); return att ? (total(logs, made) / att) * scale : null; };
  return { key, label, digits: 0, suffix: '%', value: (l) => of([l]), average: of, text: (v) => `${v.toFixed(1)}%` };
}

export const LOG_STATS: LogStat[] = [
  stat('points', 'Points', (l) => l.points), stat('rebounds', 'Rebounds', (l) => l.rebounds), stat('assists', 'Assists', (l) => l.assists), stat('steals', 'Steals', (l) => l.steals), stat('blocks', 'Blocks', (l) => l.blocks), stat('turnovers', 'Turnovers', (l) => l.turnovers),
  stat('minutes', 'Minutes', (l) => parseInt(l.minutes, 10) || 0),
  share('fg', 'FG%', (l) => l.field_goals_made, (l) => l.field_goals_attempted), share('three', '3P%', (l) => l.three_pointers_made, (l) => l.three_pointers_attempted), share('ft', 'FT%', (l) => l.free_throws_made, (l) => l.free_throws_attempted),
  share('ts', 'True shooting', (l) => l.points, (l) => 2 * (l.field_goals_attempted + 0.44 * l.free_throws_attempted)),
  stat('threes', 'Threes made', (l) => l.three_pointers_made), stat('fga', 'Shots taken', (l) => l.field_goals_attempted), stat('fta', 'Free throws taken', (l) => l.free_throws_attempted),
  stat('oreb', 'Offensive rebounds', (l) => l.oreb), stat('dreb', 'Defensive rebounds', (l) => l.dreb), stat('pf', 'Fouls', (l) => l.pf),
  stat('plus_minus', 'Plus/minus', (l) => l.plus_minus ?? 0, { signed: true }), stat('game_score', 'Game Score', gameScore, { digits: 1 }),
];
export const logStat = (key: string) => LOG_STATS.find((s) => s.key === key) ?? LOG_STATS[0];
