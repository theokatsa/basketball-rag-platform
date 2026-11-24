import { useMemo, useState } from 'react';
import { useApp } from '../AppContext';
import { LoadError, Loading, PageHead, PlayerCell, Segmented } from '../components/Common';
import { pct, signed, toZoneMap, useLeagueZones, ZoneCourt, zoneDiff, ZONES } from '../components/CourtZones';
import type { ZoneMap } from '../components/CourtZones';
import { PlayerPicker } from '../components/PlayerPicker';
import type { PlayerShotZone } from '../types';
import { useApi } from '../useApi';
import { usePersisted } from '../usePersisted';

const MINIMUM: Record<string, number> = { rim: 150, paint: 100, 'corner-L': 30, 'corner-R': 30, 'three-LC': 80, 'three-C': 60, 'three-RC': 80 };
const minimumFor = (key: string) => MINIMUM[key] ?? 25;

export function ShotLab() {
  const { byId, loading, error } = useApp();
  const { data, error: dataError } = useApi<PlayerShotZone[]>('/players/shot-zones');
  const league = useLeagueZones();
  const [tab, setTab] = usePersisted<'leaders' | 'versus'>('lab-tab', 'leaders');
  const [zone, setZone] = usePersisted('lab-zone', 'three-C');
  const [pair, setPair] = usePersisted<(number | null)[]>('lab-pair', [null, null]);
  const [hover, setHover] = useState<string | null>(null);
  const players = useMemo(() => {
    const grouped = new Map<number, PlayerShotZone[]>();
    for (const row of data ?? []) { const list = grouped.get(row.player_id); if (list) list.push(row); else grouped.set(row.player_id, [row]); }
    return new Map<number, ZoneMap>([...grouped].map(([id, rows]) => [id, toZoneMap(rows)]));
  }, [data]);
  const ranked = useMemo(() => [...players].flatMap(([id, map]) => {
    const p = byId.get(id), s = map.get(zone);
    return p && s && s.att >= minimumFor(zone) ? [{ p, s, v: s.made / s.att }] : [];
  }).sort((a, b) => b.v - a.v), [players, byId, zone]);
  if (error || dataError) return <LoadError message={(error ?? dataError)!} />;
  const base = league?.get(zone);
  const label = ZONES.find((z) => z.key === zone)?.label ?? '';
  return (
    <>
      <PageHead title="Shot Lab" intro="Who shoots best from where."><Segmented label="View" value={tab} options={[['leaders', 'Best by zone'], ['versus', 'Side by side']]} onChange={setTab} /></PageHead>
      {!data || !league || loading ? <Loading height="34rem" /> : tab === 'leaders' ? (
        <section className="panel">
          <div className="shot-chart">
            <div><ZoneCourt picker label="Pick a court zone" zones={league} league={league} hover={hover} selected={zone} onHover={setHover} onSelect={setZone} /><p className="radar-note">Click a zone. Numbers on the court are league averages.</p></div>
            <div>
              <div className="panel-header"><div><h2>{label}</h2><p>At least {minimumFor(zone)} attempts. League average {base ? pct(base.made, base.att) : '–'}</p></div><select className="control-input compact-select" aria-label="Zone" value={zone} onChange={(e) => setZone(e.target.value)}>{ZONES.map((z) => <option key={z.key} value={z.key}>{z.label}</option>)}</select></div>
              <ol className="rank-list lab-list">{ranked.slice(0, 10).map(({ p, s, v }, i) => <li key={p.player_id}><span className="rank-no">{i + 1}</span><PlayerCell player={p} note={`${s.made}/${s.att}`} /><span className="zone-diff up">{base ? signed((v - base.made / base.att) * 100) : ''}</span><b>{pct(s.made, s.att)}</b></li>)}</ol>
              {!ranked.length && <p className="status">Nobody has enough attempts here.</p>}
            </div>
          </div>
        </section>
      ) : (
        <div className="two-col">
          {[0, 1].map((slot) => {
            const id = pair[slot], other = pair[1 - slot];
            const player = id != null ? byId.get(id) : undefined;
            const map = id != null ? players.get(id) : undefined;
            const otherMap = other != null ? players.get(other) : undefined;
            return (
              <section className="panel" key={slot}>
                <PlayerPicker label={`Player ${slot + 1}`} placeholder={player ? 'Change player' : `Choose player ${slot + 1}`} exclude={other != null ? [other] : []} onPick={(pid) => setPair(pair.map((v, i) => (i === slot ? pid : v)))} />
                {!player ? <div className="empty-state"><p>Pick a player to compare.</p></div> : (
                  <>
                    <div className="versus-name"><PlayerCell player={player} /></div>
                    {!map ? <p className="status">No shots recorded.</p> : (
                      <>
                        <ZoneCourt label={`${player.full_name} by zone`} zones={map} league={league} hover={hover} onHover={setHover} />
                        <div className="zone-list versus-list">
                          {ZONES.map((z) => {
                            const s = map.get(z.key), o = otherMap?.get(z.key), d = zoneDiff(s, league.get(z.key));
                            const wins = s && o && s.att >= 5 && o.att >= 5 && s.made / s.att > o.made / o.att;
                            return <div className={`zone-row ${hover === z.key ? 'lit' : ''} ${wins ? 'wins' : ''}`} key={z.key} onMouseEnter={() => setHover(z.key)} onMouseLeave={() => setHover(null)}><span className="zone-name">{z.label}</span><span className="zone-att">{s ? `${s.made}/${s.att}` : '0'}</span><span className="zone-pct">{s ? pct(s.made, s.att) : '–'}</span><span className={`zone-diff ${d == null ? '' : d > 0 ? 'up' : 'down'}`}>{d == null ? '–' : signed(d)}</span></div>;
                          })}
                        </div>
                      </>
                    )}
                  </>
                )}
              </section>
            );
          })}
        </div>
      )}
    </>
  );
}
