import { useMemo } from 'react';
import { useApp } from '../AppContext';
import { Avatar } from '../components/Avatar';
import { LoadError, Loading } from '../components/Common';
import { signed, toZoneMap, useLeagueZones, ZoneCourt, zoneDiff, ZONES } from '../components/CourtZones';
import { BackIcon } from '../components/Icons';
import { RadarChart } from '../components/RadarChart';
import { formatStat, statByKey } from '../stats';
import type { GameLog, PlayerProfile, PlayerShotZone, SeasonStat, SimilarPlayerResult } from '../types';
import { useApi } from '../useApi';
import { formatDate, fractionPct, radarMetrics, rankLabel } from '../utils';

const NAMES: Record<string, string> = { PTS: 'scoring', REB: 'rebounding', AST: 'playmaking', STL: 'steals', BLK: 'shot blocking', 'FG%': 'field goal accuracy' };
const joinWords = (words: string[]) => (words.length > 1 ? `${words.slice(0, -1).join(', ')} and ${words[words.length - 1]}` : words[0] ?? '');

export function Report({ id }: { id: number }) {
  const { byId, totals, loading, error, open } = useApp();
  const stats = useApi<SeasonStat[]>(`/players/${id}/season-stats`);
  const profile = useApi<PlayerProfile>(`/players/${id}/profile`);
  const similar = useApi<SimilarPlayerResult[]>(`/players/${id}/similar?limit=5`);
  const logs = useApi<GameLog[]>(`/players/${id}/game-logs`);
  const shots = useApi<PlayerShotZone[]>('/players/shot-zones');
  const league = useLeagueZones();
  const zones = useMemo(() => (shots.data ? toZoneMap(shots.data.filter((r) => r.player_id === id)) : null), [shots.data, id]);
  const failed = error ?? stats.error ?? logs.error ?? shots.error;
  if (failed) return <LoadError message={failed} />;
  if (loading || !stats.data || !logs.data || !zones || (!profile.data && !profile.error) || (!similar.data && !similar.error)) return <Loading height="40rem" />;
  const player = byId.get(id);
  const s = stats.data[0];
  if (!player || !s) return <LoadError message="There are no statistics for this player." />;

  const metrics = radarMetrics(s, 'all');
  const strong = metrics.filter((m) => m.percentile != null && m.percentile <= 0.2).map((m) => NAMES[m.label]);
  const weak = metrics.filter((m) => m.percentile != null && m.percentile >= 0.6).map((m) => NAMES[m.label]);
  const zoneRows = ZONES.flatMap((z) => { const own = zones.get(z.key); const diff = zoneDiff(own, league?.get(z.key)); return own && own.att >= 20 && diff != null ? [{ label: z.label.toLowerCase(), diff }] : []; }).sort((a, b) => b.diff - a.diff);
  const bestZone = zoneRows[0];
  const worstZone = zoneRows[zoneRows.length - 1];
  const best = logs.data.reduce<GameLog | null>((top, l) => (!top || l.points > top.points ? l : top), null);
  const last = logs.data.slice(0, 10);
  const ts = statByKey('ts');
  const strengths = [
    strong.length > 0 && `Top 20% of the league in ${joinWords(strong)}.`,
    bestZone && bestZone.diff > 2 && `Best zone: ${bestZone.label}, ${signed(bestZone.diff)} percentage points against the league.`,
    `True shooting of ${formatStat(ts, ts.get(player, totals[id]))} across ${s.games_played} games.`,
    logs.data.length >= 20 && `Averaged ${(last.reduce((sum, l) => sum + l.points, 0) / last.length).toFixed(1)} points over the last 10 games (${s.points.toFixed(1)} for the season).`,
  ].filter((t): t is string => Boolean(t));
  const concerns = [
    weak.length > 0 && `In the lower 40% of the league in ${joinWords(weak)}.`,
    worstZone && worstZone.diff < -2 && `Weakest zone: ${worstZone.label}, ${signed(worstZone.diff)} percentage points against the league.`,
    s.turnovers >= 2.5 && `Commits ${s.turnovers.toFixed(1)} turnovers per game.`,
    s.games_played < 50 && `Played only ${s.games_played} games, so the sample is limited.`,
  ].filter((t): t is string => Boolean(t));
  const line: [string, string, number | null][] = [['PTS', s.points.toFixed(1), s.points_rank], ['REB', s.rebounds.toFixed(1), s.rebounds_rank], ['AST', s.assists.toFixed(1), s.assists_rank], ['STL', s.steals.toFixed(1), s.steals_rank], ['BLK', s.blocks.toFixed(1), s.blocks_rank], ['MIN', s.minutes.toFixed(1), null], ['FG%', fractionPct(s.field_goal_pct), s.field_goal_rank], ['3P%', fractionPct(s.three_point_pct), s.three_point_rank], ['FT%', fractionPct(s.free_throw_pct), s.free_throw_rank]];
  const facts = [player.club_full_name, player.position, player.age != null && `${player.age} years old`, profile.data?.height, profile.data?.weight && `${profile.data.weight} lb`].filter(Boolean).join(', ');
  return (
    <>
      <div className="detail-topbar report-actions"><button type="button" className="back-button" onClick={() => open(id)}><BackIcon />Back to profile</button><button type="button" className="submit-button" onClick={() => window.print()}>Print or save as PDF</button></div>
      <article className="report">
        <header><Avatar name={player.full_name} nbaPlayerId={player.nba_player_id} className="report-photo" /><div><p>Scouting report, {s.season}</p><h1>{player.full_name}</h1><p>{facts}</p></div></header>
        <dl className="report-stats">{line.map(([label, value, rank]) => <div key={label}><dt>{label}</dt><dd>{value}</dd><dd className="tile-note">{rank ? rankLabel(rank) : 'per game'}</dd></div>)}</dl>
        <div className="report-cols">
          <section><h2>Strengths</h2><ul>{strengths.map((b) => <li key={b}>{b}</li>)}</ul></section>
          <section><h2>Concerns</h2>{concerns.length ? <ul>{concerns.map((b) => <li key={b}>{b}</li>)}</ul> : <p>No clear statistical weakness.</p>}</section>
        </div>
        <div className="report-cols">
          <section><h2>Profile</h2><RadarChart series={[{ name: player.full_name, color: '#e85400', metrics }]} label="Percentile radar" /></section>
          <section><h2>Shooting by zone</h2><ZoneCourt label="Shooting by zone" zones={zones} league={league} /><p className="report-tops">Orange is above the league average, blue below.</p></section>
        </div>
        <div className="report-cols">
          <section><h2>Comparable players</h2><ul>{(similar.data ?? []).map((r) => <li key={r.player_id}>{r.full_name}, {Math.round(r.similarity * 100)}% match{r.shared_traits.length > 0 && ` (${r.shared_traits.slice(0, 2).join(', ')})`}</li>)}</ul></section>
          <section><h2>Season high</h2><p>{best ? `${best.points} points, ${best.rebounds} rebounds and ${best.assists} assists${best.opponent ? ` ${best.is_home ? 'against' : 'at'} ${best.opponent}` : ''}, ${formatDate(best.game_date)}.` : 'No games recorded.'}</p></section>
        </div>
      </article>
    </>
  );
}
