import { useMemo, useState } from 'react';
import { useApp } from '../AppContext';
import { formatStat, MAX_COMPARE, SERIES, STAT_GROUPS, statByKey, STATS } from '../stats';
import type { HeadToHead as Duel, PlayerScore, PlayerZoneRow } from '../types';
import { useApi } from '../useApi';
import { usePersisted } from '../usePersisted';
import { Avatar } from './Avatar';
import { LoadError, Loading, PageHead, Segmented, TeamLogo } from './Common';
import { toZoneMap, useLeagueZones, ZoneCourt, ZONES } from './CourtZones';
import { BackIcon, CloseIcon, CompareIcon } from './Icons';
import { CompareTrends, useLogs } from './CompareTrends';
import type { Entry } from './CompareTrends';
import { HeadToHead } from './HeadToHead';
import { RadarChart } from './RadarChart';

const RADAR = ['points', 'ts', 'threes', 'assists', 'ast_to', 'rebounds', 'steals', 'blocks', 'dfg_diff', 'net_rating'];

/** Share of qualified players this value beats, from 0 (worst) to 1. */
function usePercentiles() {
  const { players, totals } = useApp();
  return useMemo(() => {
    const pool = players.filter((p) => (p.games_played ?? 0) >= 20 && (p.minutes ?? 0) >= 12);
    const sorted = new Map(RADAR.map((key) => { const s = statByKey(key); return [key, pool.map((p) => s.get(p, totals[p.player_id])).filter((v): v is number => v != null).sort((a, b) => a - b)]; }));
    return (key: string, v: number | null) => {
      const values = sorted.get(key);
      if (v == null || !values?.length) return null;
      const below = values.filter((x) => x < v).length / values.length;
      return statByKey(key).lowerIsBetter ? 1 - below : below;
    };
  }, [players, totals]);
}

export function Compare({ onBack }: { onBack: () => void }) {
  const { compareIds, setCompareIds, byId, totals, loading, error, open, browse } = useApp();
  const [group, setGroup] = usePersisted<string>('cmp-group', 'All');
  const entries = useMemo<Entry[]>(() => compareIds.flatMap((id, i) => { const p = byId.get(id); return p ? [{ id, p, color: SERIES[i % SERIES.length] }] : []; }), [compareIds, byId]);
  const percentile = usePercentiles();
  const league = useLeagueZones();
  const zones = useApi<PlayerZoneRow[]>('/shots/zones');
  const scores = useApi<PlayerScore[]>('/insights/scores');
  const duels = useApi<Duel[]>(entries.length > 1 ? `/insights/head-to-head?ids=${entries.map((e) => e.id).join(',')}` : null);
  const logs = useLogs(entries);
  const [hover, setHover] = useState<string | null>(null);
  const add = () => browse({ title: 'Choose players to compare', max: MAX_COMPARE, min: 2, confirm: 'Compare players', selected: compareIds.filter((id) => byId.has(id)), onDone: setCompareIds });
  const zoneMaps = useMemo(() => new Map(entries.map((e) => [e.id, zones.data ? toZoneMap(zones.data.filter((r) => r.player_id === e.id)) : null])), [entries, zones.data]);
  if (error) return <LoadError message={error} />;
  if (loading) return <Loading height="30rem" />;
  if (!entries.length) return <><PageHead title="Compare players" intro={`Put up to ${MAX_COMPARE} players side by side.`} /><div className="empty-state"><span className="empty-mark"><CompareIcon /></span><p>Nothing to compare yet.</p><small>Pick players from a searchable list.</small><button type="button" className="submit-button" onClick={add}>Choose players</button></div></>;

  const rows = STATS.filter((s) => (group === 'All' ? s.group !== 'Other' || s.key === 'minutes' || s.key === 'games_played' : s.group === group)).map((s) => {
    const values = entries.map((e) => s.get(e.p, totals[e.id]));
    const valid = values.filter((v): v is number => v != null);
    const best = valid.length > 1 && s.group !== 'Other' ? (s.lowerIsBetter ? Math.min(...valid) : Math.max(...valid)) : null;
    return { s, values, best: valid.every((v) => v === valid[0]) ? null : best };
  });
  const wins = entries.map((_, i) => rows.filter((r) => r.best != null && r.values[i] === r.best).length);
  const scoreOf = (id: number) => scores.data?.find((s) => s.player_id === id);
  const shotLine = (id: number) => {
    const map = zoneMaps.get(id);
    if (!map) return [];
    const total = ZONES.reduce((s, z) => s + (map.get(z.key)?.att ?? 0), 0) || 1;
    return (['Paint', 'Mid-range', 'Three'] as const).map((g) => { const own = ZONES.filter((z) => z.group === g).map((z) => map.get(z.key)); const att = own.reduce((s, z) => s + (z?.att ?? 0), 0), made = own.reduce((s, z) => s + (z?.made ?? 0), 0); return { g, share: (att / total) * 100, pct: att ? (made / att) * 100 : null }; });
  };
  return (
    <>
      <PageHead title="Compare players" intro="2024-25 season. The best value in each row is marked."><div className="panel-tools"><button type="button" className="submit-button" onClick={add}>{entries.length < MAX_COMPARE ? 'Add or change players' : 'Change players'}</button><button type="button" className="back-button" onClick={onBack}><BackIcon />Back</button></div></PageHead>
      <div className="cmp-cards" style={{ gridTemplateColumns: `repeat(${Math.max(2, entries.length)}, minmax(150px, 1fr))` }}>
        {entries.map((e, i) => {
          const score = scoreOf(e.id);
          return (
            <article className="cmp-card" key={e.id} style={{ borderTopColor: e.color }}>
              <button type="button" className="icon-button small" aria-label={`Remove ${e.p.full_name}`} onClick={() => setCompareIds(compareIds.filter((id) => id !== e.id))}><CloseIcon /></button>
              <span className="cmp-logo"><TeamLogo teamId={e.p.club_team_id} size={120} /></span>
              <Avatar key={e.p.nba_player_id} name={e.p.full_name} nbaPlayerId={e.p.nba_player_id} className="podium-photo" />
              <button type="button" className="player-link" onClick={() => open(e.id)}>{e.p.full_name}</button>
              <small>{e.p.club}, {e.p.position}</small>
              <p className="cmp-line">{([['points', 'pts'], ['rebounds', 'reb'], ['assists', 'ast']] as const).map(([k, label]) => <span key={k}><b>{e.p[k]?.toFixed(1)}</b>{label}</span>)}</p>
              {score && <p className="cmp-scores"><span>Overall <b>{score.score}</b></span><span>Offense <b>{score.offense}</b></span><span>Defense <b>{score.defense}</b></span></p>}
              {entries.length > 1 && <p className="cmp-wins">Best in {wins[i]} of {rows.filter((r) => r.best != null).length}</p>}
            </article>
          );
        })}
        {entries.length === 1 && <button type="button" className="cmp-card add" onClick={add}><span className="choose-plus" aria-hidden="true">+</span>Add a player</button>}
      </div>
      <p className="radar-note">Scores rank each player from 0 to 100 among regular rotation players, from box score, advanced and shot-defense statistics.</p>

      <div className="compare-body wide">
        <section className="panel">
          <div className="panel-header"><div><h2>Profile</h2><p>Further out is better. Percentile among rotation players.</p></div></div>
          <RadarChart label="Percentile comparison" series={entries.map((e) => ({ name: e.p.full_name, color: e.color, metrics: RADAR.map((key) => { const v = percentile(key, statByKey(key).get(e.p, totals[e.id])); return { label: statByKey(key).short, percentile: v == null ? null : 1 - v }; }) }))} />
          <div className="scatter-legend centered">{entries.map((e) => <span key={e.id}><i style={{ background: e.color }} />{e.p.full_name}</span>)}</div>
        </section>
        <section className="panel">
          <div className="panel-header"><h2>Numbers</h2></div>
          <div className="filter-bar"><Segmented label="Category" value={group} options={[['All', 'All'], ...STAT_GROUPS.map((g) => [g, g] as [string, string])]} onChange={setGroup} /></div>
          <div className="detail-records-scroll cmp-scroll">
            <table className="detail-records-table compare-table" style={{ minWidth: 170 + entries.length * 96 }}>
              <thead><tr><th scope="col">Per game</th>{entries.map((e) => <th scope="col" key={e.id} style={{ borderBottom: `3px solid ${e.color}` }}>{e.p.full_name}</th>)}</tr></thead>
              <tbody>
                {rows.map(({ s, values, best }, r) => {
                  const most = Math.max(...values.map((v) => Math.abs(v ?? 0)), 0.0001);
                  return [group === 'All' && s.group !== rows[r - 1]?.s.group && <tr key={`g${r}`} className="cmp-group"><th scope="rowgroup" colSpan={entries.length + 1}>{s.group}</th></tr>, <tr key={s.key}><th scope="row">{s.label}</th>{values.map((v, i) => <td key={entries[i].id} className={best != null && v === best ? 'best' : ''}>{formatStat(s, v)}{best != null && v === best && <span className="best-mark" aria-label="best">★</span>}<i className="cmp-bar"><em style={{ width: `${(Math.abs(v ?? 0) / most) * 100}%`, background: entries[i].color }} /></i></td>)}</tr>];
                })}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <CompareTrends entries={entries} logs={logs} />

      <section className="panel">
        <div className="panel-header"><div><h2>Shooting by zone</h2><p>Orange is above the league average, blue below. Hover a zone to compare it.</p></div></div>
        {zones.error ? <p className="status error">{zones.error}</p> : !zones.data || !league ? <Loading /> : (
          <div className="cmp-courts">
            {entries.map((e) => (
              <div key={e.id}>
                <p className="cmp-court-name"><i style={{ background: e.color }} />{e.p.full_name}</p>
                <ZoneCourt label={`${e.p.full_name} by zone`} zones={zoneMaps.get(e.id)!} league={league} hover={hover} onHover={setHover} />
                <p className="cmp-hover">{hover ? (() => { const z = zoneMaps.get(e.id)?.get(hover); return `${ZONES.find((k) => k.key === hover)?.label}: ${z ? `${z.made}/${z.att}, ${((z.made / z.att) * 100).toFixed(1)}%` : 'no shots'}`; })() : ' '}</p>
                <dl className="mix">{shotLine(e.id).map((m) => <div key={m.g}><dt>{m.g}</dt><dd>{m.share.toFixed(0)}% of shots<small>{m.pct == null ? '–' : `${m.pct.toFixed(1)}% made`}</small></dd></div>)}</dl>
              </div>
            ))}
          </div>
        )}
      </section>

      {entries.length > 1 && <HeadToHead entries={entries} logs={logs} duels={duels.error ? [] : duels.data} />}
    </>
  );
}
