import type { SeasonStat } from './types';

export const playerImage = (nbaPlayerId: number) => `https://cdn.nba.com/headshots/nba/latest/1040x760/${nbaPlayerId}.png`;
export const teamLogo = (teamId: number | null) => (teamId ? `https://cdn.nba.com/logos/nba/${teamId}/primary/L/logo.svg` : null);

export function rankLabel(rank: number | null): string {
  if (rank == null) return '';
  const suffix = rank % 100 >= 11 && rank % 100 <= 13 ? 'th' : rank % 10 === 1 ? 'st' : rank % 10 === 2 ? 'nd' : rank % 10 === 3 ? 'rd' : 'th';
  return `${rank}${suffix}`;
}

/** Season stats store shooting percentages as fractions (0.452). */
export const fractionPct = (value: number | null) => (value == null ? '-' : `${(value * 100).toFixed(1)}%`);

export function loadStored<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function saveStored(key: string, value: unknown) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* storage unavailable */ }
}

export type RadarMetric = { label: string; percentile: number | null };

/** Percentiles from the API are "top fraction": 0 is best, 1 is worst. */
export function radarMetrics(stat: SeasonStat, scope: 'all' | 'position'): RadarMetric[] {
  return scope === 'position'
    ? [
        { label: 'PTS', percentile: stat.position_points_percentile }, { label: 'REB', percentile: stat.position_rebounds_percentile },
        { label: 'AST', percentile: stat.position_assists_percentile }, { label: 'STL', percentile: stat.position_steals_percentile },
        { label: 'BLK', percentile: stat.position_blocks_percentile }, { label: 'FG%', percentile: stat.position_field_goal_percentile },
      ]
    : [
        { label: 'PTS', percentile: stat.points_percentile }, { label: 'REB', percentile: stat.rebounds_percentile },
        { label: 'AST', percentile: stat.assists_percentile }, { label: 'STL', percentile: stat.steals_percentile },
        { label: 'BLK', percentile: stat.blocks_percentile }, { label: 'FG%', percentile: stat.field_goal_percentile },
      ];
}

/** API percentiles are the "top fraction" (0.03 = top 3%). Never show "Top 0%". */
export const topLabel = (percentile: number | null) => (percentile == null ? 'n/a' : `Top ${Math.max(1, Math.round(percentile * 100))}%`);

/** Shot matchups are stored as "HOME vs AWAY"; show them as "AWAY @ HOME". */
export function formatMatchup(matchup: string): string {
  const [home, away] = matchup.split(' vs ');
  return away ? `${away} @ ${home}` : matchup;
}

export const formatDate = (value: string | null) => (value ? new Date(`${value}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '–');

/** Lower-case without accents, so "doncic" finds "Dončić". */
export const plain = (value: string) => value.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
