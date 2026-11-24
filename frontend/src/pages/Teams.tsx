import { useMemo, useState } from 'react';
import { useApp } from '../AppContext';
import { LoadError, Loading, PageHead, PlayerCell, RowActions, TeamLogo } from '../components/Common';
import { toZoneMap, useLeagueZones, ZoneCourt, zoneDiff, ZONES, pct, signed, fillFor } from '../components/CourtZones';
import { BackIcon } from '../components/Icons';
import type { PlayerDirectoryRow, TeamShotZone } from '../types';
import { formatStat, statByKey } from '../stats';
import { useApi } from '../useApi';

function useTeams() {
  const { players } = useApp();
  return useMemo(() => {
    const map = new Map<number, { id: number; name: string; abbr: string; roster: PlayerDirectoryRow[] }>();
    for (const p of players) {
      if (p.club_team_id == null) continue;
      const team = map.get(p.club_team_id) ?? { id: p.club_team_id, name: p.club_full_name ?? '', abbr: p.club ?? '', roster: [] };
      team.roster.push(p);
      map.set(p.club_team_id, team);
    }
    for (const team of map.values()) team.roster.sort((a, b) => (b.points ?? 0) - (a.points ?? 0));
    return [...map.values()].sort((a, b) => a.name.localeCompare(b.name));
  }, [players]);
}

export function Teams() {
  const { loading, error, go } = useApp();
  const teams = useTeams();
  if (error) return <LoadError message={error} />;
  return (
    <>
      <PageHead title="Teams" intro="Rosters as of each player's last 2024-25 team." />
      {loading ? <Loading /> : (
        <div className="team-grid">
          {teams.map((team) => (
            <button type="button" className="team-card" key={team.id} onClick={() => go('team', team.id)}>
              <TeamLogo teamId={team.id} size={56} />
              <span><b>{team.name}</b><small>{team.roster.length} players. Top scorer: {team.roster[0]?.full_name}, {team.roster[0]?.points?.toFixed(1)}</small></span>
            </button>
          ))}
        </div>
      )}
    </>
  );
}

export function Team({ id }: { id: number }) {
  const { loading, error, totals, go } = useApp();
  const team = useTeams().find((t) => t.id === id);
  const shots = useApi<TeamShotZone[]>('/players/team-shot-zones');
  const league = useLeagueZones();
  const [hover, setHover] = useState<string | null>(null);
  const zones = useMemo(() => (shots.data ? toZoneMap(shots.data.filter((r) => r.team_id === id)) : null), [shots.data, id]);
  if (error) return <LoadError message={error} />;
  if (loading) return <Loading height="30rem" />;
  if (!team) return <LoadError message="This team was not found." />;
  return (
    <>
      <div className="detail-topbar team-back"><button type="button" className="back-button" onClick={() => go('teams')}><BackIcon />All teams</button></div>
      <header className="team-hero"><TeamLogo teamId={team.id} size={110} /><div><h1>{team.name}</h1><p>{team.roster.length} players</p></div></header>
      <div className="team-leaders">
        {['points', 'rebounds', 'assists', 'steals', 'blocks'].map((key) => {
          const stat = statByKey(key);
          const leader = [...team.roster].filter((p) => (p.games_played ?? 0) >= 20).sort((a, b) => (stat.get(b) ?? 0) - (stat.get(a) ?? 0))[0];
          return leader && <div className="panel" key={key}><small>{stat.label}</small><strong>{formatStat(stat, stat.get(leader))}</strong><PlayerCell player={leader} note="" /></div>;
        })}
      </div>
      <section className="panel">
        <div className="panel-header"><div><h2>Team shooting</h2><p>FG% against the league average from each zone</p></div></div>
        {shots.error ? <p className="status error">{shots.error}</p> : !zones ? <Loading /> : (
          <div className="shot-chart">
            <ZoneCourt label={`${team.name} shooting by zone`} zones={zones} league={league} hover={hover} onHover={setHover} />
            <div className="zone-list">
              {ZONES.map((z) => { const s = zones.get(z.key); const d = zoneDiff(s, league?.get(z.key)); return <div key={z.key} className={`zone-row ${hover === z.key ? 'lit' : ''}`} onMouseEnter={() => setHover(z.key)} onMouseLeave={() => setHover(null)}><i style={{ background: fillFor(d) }} /><span className="zone-name">{z.label}</span><span className="zone-att">{s ? `${s.made}/${s.att}` : '0'}</span><span className="zone-pct">{s ? pct(s.made, s.att) : '–'}</span><span className={`zone-diff ${d == null ? '' : d > 0 ? 'up' : 'down'}`}>{d == null ? '–' : signed(d)}</span></div>; })}
            </div>
          </div>
        )}
      </section>
      <section className="panel">
        <div className="panel-header"><h2>Roster</h2></div>
        <div className="detail-records-scroll open">
          <table className="detail-records-table roster-table">
            <thead><tr>{['Player', 'Age', 'GP', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'FG%', '3P%', '+/−', ''].map((h, i) => <th scope="col" key={i}>{h}</th>)}</tr></thead>
            <tbody>{team.roster.map((p) => <tr key={p.player_id}><th scope="row"><PlayerCell player={p} note={p.position ?? ''} /></th><td>{p.age ?? '–'}</td><td>{p.games_played}</td>{['minutes', 'points', 'rebounds', 'assists', 'steals', 'blocks', 'fg', 'three', 'plus_minus'].map((k) => <td key={k}>{formatStat(statByKey(k), statByKey(k).get(p, totals[p.player_id]))}</td>)}<td><RowActions player={p} /></td></tr>)}</tbody>
          </table>
        </div>
      </section>
    </>
  );
}
