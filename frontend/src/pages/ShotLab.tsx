import { useMemo, useState } from 'react';
import { useApp } from '../AppContext';
import { Avatar } from '../components/Avatar';
import { LoadError, Loading, PageHead, PlayerCell, Segmented, TeamLogo } from '../components/Common';
import { isThreeZone, pct, signed, toZoneMap, useLeagueZones, ZoneCourt, ZoneList, zoneLabel, ZONES } from '../components/CourtZones';
import type { ZoneMap } from '../components/CourtZones';
import { Dropdown, TeamSelect } from '../components/Dropdown';
import { Pagination, usePaged } from '../components/Pagination';
import { playsPosition, POSITIONS } from '../stats';
import type { Defenders, Matchup, PlayerZoneRow } from '../types';
import { useApi } from '../useApi';
import { usePersisted } from '../usePersisted';

const MINIMUM: Record<string, number> = { rim: 120, 'lane-low': 60, 'lane-high': 40, top: 40, 'slot-L': 60, 'slot-R': 60, 'wing-L': 40, 'wing-R': 40, deep: 25 };
const minimumFor = (key: string) => MINIMUM[key] ?? 20;
/** Attempts at the league average mixed into every player, so 12 for 20 does not outrank 120 for 220. */
const priorFor = (key: string) => (key === 'rim' || key === 'lane-low' ? 60 : 40);

type Sort = 'adjusted' | 'raw' | 'made' | 'added';

function Leaders() {
  const { byId } = useApp();
  const [opponent, setOpponent] = usePersisted('lab-opp', '');
  const { data, error } = useApi<PlayerZoneRow[]>(`/shots/zones${opponent ? `?opponent=${opponent}` : ''}`);
  const league = useLeagueZones();
  const [zone, setZone] = usePersisted('lab-area', 'ft');
  const [sort, setSort] = usePersisted<Sort>('lab-sort', 'adjusted');
  const [position, setPosition] = usePersisted('lab-pos', '');
  const [hover, setHover] = useState<string | null>(null);
  const base = league?.get(zone);
  const average = base ? base.made / base.att : 0;
  const worth = isThreeZone(zone) ? 3 : 2;
  /** Against one team every attempt counts: the adjusted % already pulls small samples to the average. */
  const minimum = opponent ? 1 : minimumFor(zone);
  const ranked = useMemo(() => (data ?? []).filter((r) => r.zone === zone && r.attempts >= minimum).flatMap((r) => {
    const p = byId.get(r.player_id);
    if (!p || !playsPosition(p, position)) return [];
    const adjusted = (r.made + priorFor(zone) * average) / (r.attempts + priorFor(zone));
    return [{ p, r, raw: r.made / r.attempts, adjusted, added: (r.made - r.attempts * average) * worth }];
  }).sort((a, b) => (sort === 'raw' ? b.raw - a.raw : sort === 'made' ? b.r.made - a.r.made : sort === 'added' ? b.added - a.added : b.adjusted - a.adjusted)), [data, byId, zone, position, sort, minimum, average, worth]);
  const paged = usePaged(ranked, 10, [zone, sort, position, opponent].join('|'));
  /** The court shows the shots that match the filters; colours compare them with the whole league. */
  const filtered = useMemo(() => (data ? toZoneMap(data.filter((r) => { const p = byId.get(r.player_id); return p != null && playsPosition(p, position); })) : null), [data, byId, position]);
  const scope = [position && `${position.toLowerCase()}s`, opponent && `against ${opponent}`].filter(Boolean).join(' ');
  if (error) return <LoadError message={error} />;
  if (!league) return <Loading height="34rem" />;
  return (
    <section className="panel">
      <div className="shot-chart">
        <div>
          <ZoneCourt picker label="Pick a court zone" zones={filtered ?? league} league={league} hover={hover} selected={zone} onHover={setHover} onSelect={setZone} />
          <p className="radar-note">Click a zone. {scope ? <>Numbers on the court are shots by <b>{scope}</b>; warm zones are better than the league average, cool ones worse.</> : 'Numbers on the court are the whole league.'} The zones come from shot coordinates and cover the whole half court.</p>
        </div>
        <div>
          <div className="panel-header"><div><h2>{zoneLabel(zone)}</h2><p>{opponent ? 'Every shot against this team counts; sort by Adjusted % to discount one-off makes.' : `At least ${minimum} attempts.`} League average {base ? pct(base.made, base.att) : '–'}, {(average * worth).toFixed(2)} points per shot</p></div></div>
          <div className="filter-bar lab-tools">
            <Dropdown label="Zone" value={zone} options={ZONES.map((z) => ({ value: z.key, label: z.label, group: z.group }))} onChange={setZone} />
            <TeamSelect value={opponent} onChange={setOpponent} by="abbr" all="Against everyone" label="Against" />
            <Segmented label="Position" value={position} options={[['', 'All'], ...POSITIONS.map((p) => [p, `${p}s`] as [string, string])]} onChange={setPosition} />
            <Segmented label="Rank by" value={sort} options={[['adjusted', 'Adjusted %'], ['raw', 'FG%'], ['made', 'Made'], ['added', 'Points added']]} onChange={setSort} />
          </div>
          {!data ? <Loading /> : (
            <div className="lab-table">
              <div className="lab-head"><span /><span>Player</span><span>Made</span><span>FG%</span><span title="Pulled toward the league average when there are few attempts">Adjusted</span><span title="Points beyond what an average shooter scores on the same shots">Pts added</span></div>
              {paged.items.map(({ p, r, raw, adjusted, added }, i) => <div className="lab-line" key={p.player_id}><span className="rank-no">{paged.offset + i + 1}</span><PlayerCell player={p} /><span>{r.made}/{r.attempts}</span><span>{(raw * 100).toFixed(1)}%</span><b>{(adjusted * 100).toFixed(1)}%</b><span className={added > 0 ? 'zone-diff up' : 'zone-diff down'}>{signed(added)}</span></div>)}
              {!ranked.length && <p className="status">{opponent ? 'Nobody shot from here against this team.' : 'Nobody has enough attempts here.'}</p>}
            </div>
          )}
          <Pagination page={paged.page} pageCount={paged.pageCount} onPage={paged.onPage} label="Shooter pages" />
        </div>
      </div>
    </section>
  );
}

/** A big button that opens the player list. */
export function ChoosePlayer({ id, label, exclude = [], onPick }: { id: number | null; label: string; exclude?: number[]; onPick: (id: number) => void }) {
  const { byId, browse } = useApp();
  const p = id != null ? byId.get(id) : undefined;
  return (
    <button type="button" className={`choose-player ${p ? 'set' : ''}`} onClick={() => browse({ title: label, max: 1, exclude, onDone: ([picked]) => onPick(picked) })}>
      {p ? <><Avatar key={p.nba_player_id} name={p.full_name} nbaPlayerId={p.nba_player_id} className="recent-photo" /><span><b>{p.full_name}</b><small>{p.club_full_name}, {p.position}</small></span><TeamLogo teamId={p.club_team_id} size={36} /><em>Change</em></> : <><span className="choose-plus" aria-hidden="true">+</span><span><b>{label}</b><small>Browse by team, position or statistic</small></span></>}
    </button>
  );
}

function Versus() {
  const [pair, setPair] = usePersisted<(number | null)[]>('lab-pair', [null, null]);
  const [opponent, setOpponent] = usePersisted('lab-versus-opp', '');
  const { data, error } = useApi<PlayerZoneRow[]>(`/shots/zones${opponent ? `?opponent=${opponent}` : ''}`);
  const league = useLeagueZones();
  const [hover, setHover] = useState<string | null>(null);
  const maps = useMemo(() => pair.map((id) => (id != null && data ? toZoneMap(data.filter((r) => r.player_id === id)) : undefined)), [pair, data]);
  if (error) return <LoadError message={error} />;
  const summary = (map: ZoneMap) => {
    let att = 0, made = 0, points = 0, expected = 0;
    for (const z of ZONES) {
      const s = map.get(z.key), b = league?.get(z.key), value = z.group === 'Three' ? 3 : 2;
      if (!s) continue;
      att += s.att; made += s.made; points += s.made * value;
      if (b) expected += s.att * (b.made / b.att) * value;
    }
    return att ? { att, made, pps: points / att, xpps: expected / att } : null;
  };
  return (
    <>
      <div className="filter-bar"><TeamSelect value={opponent} onChange={setOpponent} by="abbr" all="Against everyone" label="Against" /><span className="count-label">Bold zones are where that player is the better shooter (10 attempts each)</span></div>
      <div className="two-col">
        {[0, 1].map((slot) => {
          const map = maps[slot], s = map && summary(map);
          return (
            <section className="panel" key={slot}>
              <ChoosePlayer id={pair[slot]} label={`Choose player ${slot + 1}`} exclude={pair[1 - slot] != null ? [pair[1 - slot]!] : []} onPick={(pid) => setPair(pair.map((v, i) => (i === slot ? pid : v)))} />
              {pair[slot] != null && (!map || !league ? <Loading /> : !s ? <p className="status">No shots recorded here.</p> : (
                <>
                  <div className="shot-summary four"><div><strong>{pct(s.made, s.att)}</strong><span>FG {s.made}/{s.att}</span></div><div><strong>{s.pps.toFixed(2)}</strong><span>Points per shot</span></div><div><strong>{s.xpps.toFixed(2)}</strong><span title="What an average shooter would score on the same shots">Shot quality</span></div><div><strong>{signed(s.pps - s.xpps, 2)}</strong><span>Shot making</span></div></div>
                  <ZoneCourt label="Shooting by zone" zones={map} league={league} hover={hover} onHover={setHover} />
                  <ZoneList zones={map} league={league} hover={hover} onHover={setHover} other={maps[1 - slot]} />
                </>
              ))}
            </section>
          );
        })}
      </div>
    </>
  );
}

function MatchupTable({ rows, expected }: { rows: Matchup[]; expected: boolean }) {
  const { byId } = useApp();
  const [sort, setSort] = useState<'possessions' | 'low' | 'high'>('possessions');
  const [minimum, setMinimum] = useState('25');
  const list = useMemo(() => rows.filter((m) => m.possessions >= Number(minimum)).sort((a, b) => (sort === 'low' ? a.edge - b.edge : sort === 'high' ? b.edge - a.edge : b.possessions - a.possessions)), [rows, sort, minimum]);
  const paged = usePaged(list, 10, `${sort}${minimum}${rows.length}`);
  return (
    <>
      <div className="filter-bar">
        <Segmented label="Order" value={sort} options={[['possessions', 'Most faced'], ['low', 'Fewest points'], ['high', 'Most points']]} onChange={setSort} />
        <Segmented label="Minimum possessions" value={minimum} options={[['10', '10+ poss.'], ['25', '25+'], ['50', '50+']]} onChange={setMinimum} />
      </div>
      <div className="lab-table">
        <div className="lab-head"><span /><span>Player</span><span>Poss.</span><span>FG</span><span>Per 100</span><span title="Against the scorer's own average; small samples count less">Diff.</span></div>
        {paged.items.map((m, i) => { const p = byId.get(m.other_id); return p && <div className="lab-line" key={m.other_id}><span className="rank-no">{paged.offset + i + 1}</span><PlayerCell player={p} /><span>{m.possessions.toFixed(0)}</span><span>{m.fgm}/{m.fga}</span><b title={expected ? `Usually ${m.expected.toFixed(0)}` : undefined}>{m.per100.toFixed(0)}</b><span className={m.edge > 0 ? 'zone-diff up' : 'zone-diff down'}>{signed(m.edge)}</span></div>; })}
        {!list.length && <p className="status">No matchups with this many possessions.</p>}
      </div>
      <Pagination page={paged.page} pageCount={paged.pageCount} onPage={paged.onPage} label="Matchup pages" />
    </>
  );
}

function DefenderTab() {
  const [id, setId] = usePersisted<number | null>('lab-defender', null);
  const { data, error } = useApi<Defenders>(id != null ? `/insights/players/${id}/defenders` : null);
  return (
    <>
      <section className="panel"><ChoosePlayer id={id} label="Choose a player" onPick={setId} />{data?.baseline != null && <p className="radar-note">Scores {data.baseline.toFixed(1)} points per 100 possessions of tracked matchups over the season. A matchup is the time one defender guards this player, as recorded by the NBA.</p>}</section>
      {error ? <LoadError message={error} /> : id == null ? <div className="empty-state"><p>Pick a player to see who guards them, and how it goes.</p></div> : !data ? <Loading height="24rem" /> : (
        <div className="two-col">
          <section className="panel"><div className="panel-header"><div><h2>Guarded by</h2><p>Points scored while this defender was on them</p></div></div><MatchupTable rows={data.guarded_by} expected={false} /></section>
          <section className="panel"><div className="panel-header"><div><h2>When defending</h2><p>Points allowed to each scorer, against that scorer’s average</p></div></div><MatchupTable rows={data.guarded} expected /></section>
        </div>
      )}
    </>
  );
}

export function ShotLab() {
  const { loading, error } = useApp();
  const [tab, setTab] = usePersisted<'leaders' | 'versus' | 'defenders'>('lab-tab', 'leaders');
  if (error) return <LoadError message={error} />;
  return (
    <>
      <PageHead title="Shot Lab" intro="Who shoots best from where, and against which defenders."><Segmented label="View" value={tab} options={[['leaders', 'Best by zone'], ['versus', 'Side by side'], ['defenders', 'Defenders']]} onChange={setTab} /></PageHead>
      {loading ? <Loading height="34rem" /> : tab === 'leaders' ? <Leaders /> : tab === 'versus' ? <Versus /> : <DefenderTab />}
    </>
  );
}
