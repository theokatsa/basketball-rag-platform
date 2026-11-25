import { useEffect, useState } from 'react';
import { useApp } from '../AppContext';
import { Avatar } from '../components/Avatar';
import { LoadError, Loading, PageHead, PlayerCell, TeamLogo } from '../components/Common';
import { signed } from '../components/CourtZones';
import { Dropdown, useTeamList } from '../components/Dropdown';
import { CloseIcon } from '../components/Icons';
import { SERIES } from '../stats';
import type { LineupResult } from '../types';
import { send } from '../useApi';
import { usePersisted } from '../usePersisted';

const EMPTY: (number | null)[] = [null, null, null, null, null];
/** Where each place sits on the half court, in percent. */
const SPOTS: [string, string, number, number][] = [['Point guard', 'Guard', 50, 80], ['Shooting guard', 'Guard', 16, 62], ['Small forward', 'Forward', 84, 62], ['Power forward', 'Forward', 27, 25], ['Center', 'Center', 69, 22]];

export function Lineup() {
  const { byId, players, loading, error, open, browse } = useApp();
  const teams = useTeamList();
  const [slots, setSlots] = usePersisted<(number | null)[]>('lineup', EMPTY);
  const [result, setResult] = useState<{ key: string; data: LineupResult | null; error: string | null } | null>(null);
  const ids = slots.filter((id): id is number => id != null);
  const key = ids.length === 5 ? ids.join(',') : '';
  useEffect(() => {
    if (!key) return;
    let cancelled = false;
    send<LineupResult>('POST', '/insights/lineup', { player_ids: key.split(',').map(Number) })
      .then((data) => { if (!cancelled) setResult({ key, data, error: null }); })
      .catch((err: Error) => { if (!cancelled) setResult({ key, data: null, error: err.message }); });
    return () => { cancelled = true; };
  }, [key]);
  if (error) return <LoadError message={error} />;
  const current = result?.key === key ? result : null;
  const data = current?.data;
  const set = (i: number, id: number | null) => setSlots(slots.map((v, k) => (k === i ? id : v)));
  const pick = (i: number) => browse({ title: `Choose a ${SPOTS[i][0].toLowerCase()}`, max: 1, position: SPOTS[i][1], exclude: ids.filter((id) => id !== slots[i]), onDone: ([id]) => set(i, id) });
  const many = () => browse({ title: 'Choose five players', max: 5, min: 1, confirm: 'Use these players', selected: ids, onDone: (list) => setSlots(EMPTY.map((_, i) => list[i] ?? null)) });
  const fromTeam = (name: string) => {
    const top = players.filter((p) => p.club_full_name === name && (p.games_played ?? 0) >= 20).sort((a, b) => (b.minutes ?? 0) - (a.minutes ?? 0)).slice(0, 5);
    const size = (p: (typeof top)[number]) => { const list = (p.position ?? '').split('-').map((x) => ['Guard', 'Forward', 'Center'].indexOf(x)); return list.reduce((s, n) => s + n, 0) / list.length; };
    setSlots(EMPTY.map((_, i) => top.sort((a, b) => size(a) - size(b))[i]?.player_id ?? null));
  };
  const name = (id: number) => byId.get(id)?.full_name ?? '';
  const ups = (data?.stats ?? []).filter((s) => s.z >= 1).sort((a, b) => b.z - a.z), downs = (data?.stats ?? []).filter((s) => s.z <= -1).sort((a, b) => a.z - b.z);
  return (
    <>
      <PageHead title="Lineup Builder" intro="Put five players on the floor and see how the group should play.">
        <div className="panel-tools">
          <Dropdown label="Load a team" value="" options={[{ value: '', label: 'Load a team’s five' }, ...teams.map((t) => ({ value: t.name, label: t.name, note: t.abbr, icon: <TeamLogo teamId={t.id} size={24} /> }))]} onChange={(v) => v && fromTeam(v)} search="Search teams" wide />
          <button type="button" className="submit-button" onClick={many}>Choose from a list</button>
          {ids.length > 0 && <button type="button" className="ghost-button" onClick={() => setSlots(EMPTY)}>Clear</button>}
        </div>
      </PageHead>
      <section className="lineup-floor" aria-label="The five places">
        <svg viewBox="-254 -56 508 478" preserveAspectRatio="none" aria-hidden="true"><g className="court-lines" fill="none"><rect x={-250} y={-52} width={500} height={470} /><rect x={-80} y={-52} width={160} height={190} /><circle cx={0} cy={138} r={60} /><path d="M-40 -8V0A40 40 0 0 0 40 0V-8" /><circle r={7.5} className="court-hoop" /><path d="M-220 -52V89.5A237.5 237.5 0 0 0 220 89.5V-52" /></g></svg>
        {slots.map((id, i) => {
          const p = id != null ? byId.get(id) : undefined;
          const [label, , x, y] = SPOTS[i];
          return (
            <div className={`floor-spot ${p ? 'filled' : ''}`} key={i} style={{ left: `${x}%`, top: `${y}%` }}>
              {p ? (
                <>
                  <button type="button" className="icon-button small" aria-label={`Remove ${p.full_name}`} onClick={() => set(i, null)}><CloseIcon /></button>
                  <button type="button" className="floor-photo" title="Change player" aria-label={`Change ${p.full_name}`} onClick={() => pick(i)}><Avatar key={p.nba_player_id} name={p.full_name} nbaPlayerId={p.nba_player_id} className="recent-photo" /></button>
                  <button type="button" className="player-link" onClick={() => open(p.player_id)}>{p.full_name}</button>
                  <small><TeamLogo teamId={p.club_team_id} size={16} />{p.position}, {p.points?.toFixed(1)} pts</small>
                </>
              ) : <button type="button" className="floor-add" onClick={() => pick(i)}><span className="choose-plus" aria-hidden="true">+</span><b>{label}</b></button>}
            </div>
          );
        })}
      </section>
      {loading ? <Loading /> : !key ? <div className="empty-state"><p>{5 - ids.length} more {5 - ids.length === 1 ? 'player' : 'players'} to go.</p><small>The analysis appears once all five places are filled.</small></div> : current?.error ? <p className="status error" role="alert">{current.error}</p> : !data ? <Loading height="30rem" /> : (
        <>
          <div className="lineup-head">
            {([['Offense', data.offense, data.offense - data.league, true], ['Defense', data.defense, data.league - data.defense, true], ['Net', data.net, data.net, false]] as const).map(([label, v, better, rating]) => <div className="panel" key={label}><small>{label}</small><strong className={better > 1 ? 'up' : better < -1 ? 'down' : ''}>{rating ? v.toFixed(1) : signed(v)}</strong><span>{rating ? `${Math.abs(better).toFixed(1)} ${better >= 0 ? 'better' : 'worse'} than average (${data.league.toFixed(1)})` : 'points per 100 possessions'}</span></div>)}
            {data.average_height && <div className="panel"><small>Average height</small><strong>{Math.floor(data.average_height / 12)}&apos;{(data.average_height % 12).toFixed(1)}&quot;</strong><span>{Math.round(data.average_height * 2.54)} cm</span></div>}
          </div>
          <div className="two-col">
            <section className="panel"><h2>Strengths</h2><p className="verdict">{ups.map((s) => s.label.toLowerCase()).join(', ') || 'Nothing clearly above average.'}</p><h2 className="second">Weak points</h2><p className="verdict">{downs.map((s) => s.label.toLowerCase()).join(', ') || 'Nothing clearly below average.'}</p></section>
            <section className="panel"><h2>Balance</h2><div className="balance">{data.checks.map((c) => <div key={c.label} className={c.players.length >= c.target ? 'ok' : 'short'}><span className="balance-mark" aria-hidden="true">{c.players.length >= c.target ? '✓' : '!'}</span><span><b>{c.label}: {c.players.length}, {c.players.length >= c.target ? 'enough' : `${c.target} is a good target`}</b><small>{c.players.map(name).join(', ') || c.note}</small></span></div>)}</div></section>
          </div>
          <section className="panel">
            <div className="panel-header"><div><h2>Who gets the ball</h2><p>Their usual shares add up to {data.total_usage.toFixed(0)}%, so they are scaled to 100. {data.total_usage > 100 ? 'Players who give up shots become a little more efficient.' : 'Players who take on more shots become a little less efficient.'}</p></div></div>
            <div className="share-bar" role="img" aria-label={data.shares.map((s) => `${name(s.player_id)} ${s.in_lineup.toFixed(0)}%`).join(', ')}>{data.shares.map((s, i) => <i key={s.player_id} style={{ width: `${s.in_lineup}%`, background: SERIES[i] }} />)}</div>
            <div className="share-list">{data.shares.map((s, i) => { const p = byId.get(s.player_id); return p && <div key={s.player_id}><i style={{ background: SERIES[i] }} /><PlayerCell player={p} note={`${s.own.toFixed(0)}% usually, ${s.in_lineup.toFixed(0)}% here`} /><span><b>{s.points_per_100.toFixed(0)}</b><small>points per 100 uses ({signed(s.points_per_100 - s.own_points_per_100)})</small></span></div>; })}</div>
          </section>
          <section className="panel">
            <div className="panel-header"><div><h2>Against an average lineup</h2><p>The middle line is an average five. Right is better.</p></div></div>
            <div className="z-rows">{data.stats.map((s) => <div key={s.label} title={s.note}><span>{s.label}{s.note && <small>{s.note}</small>}</span><i><em className={s.z >= 0 ? 'up' : 'down'} style={s.z >= 0 ? { left: '50%', width: `${Math.min(50, s.z * 12.5)}%` } : { right: '50%', width: `${Math.min(50, -s.z * 12.5)}%` }} /></i><b>{s.own.toFixed(1)}</b><small>avg {s.base.toFixed(1)}</small></div>)}</div>
          </section>
          {data.pairs.length > 0 && <section className="panel"><div className="panel-header"><div><h2>They have played together</h2><p>Real net rating with both on the court in 2024-25</p></div></div><div className="pair-grid">{data.pairs.sort((a, b) => b.net_rating - a.net_rating).map((x) => <div key={`${x.player_a}${x.player_b}`}><span>{name(x.player_a)} and {name(x.player_b)}</span><b className={x.net_rating > 0 ? 'up' : 'down'}>{signed(x.net_rating)}</b><small>{x.minutes.toFixed(0)} min</small></div>)}</div></section>}
          <section className="panel">
            <div className="panel-header"><div><h2>Opponents, position by position</h2><p>Players at the same position, from overall statistics, size and real matchups where they exist</p></div></div>
            <div className="opp-grid">
              <div className="opp-head"><span>Your player</span><span>Hardest to face</span><span>Best to face</span></div>
              {data.opponents.map((o) => { const p = byId.get(o.player_id); const side = (list: typeof o.toughest) => <div className="opp-side">{list.map((x) => { const r = byId.get(x.player_id); return r && <div key={x.player_id}><PlayerCell player={r} /><small>{x.notes.join('. ')}.</small></div>; })}</div>; return p && <div className="opp-row" key={o.player_id}><PlayerCell player={p} />{side(o.toughest)}{side(o.easiest)}</div>; })}
            </div>
            <p className="radar-note">Planned: replace these rules with a model trained on lineup results, so it can learn which players win their matchups.</p>
          </section>
          <p className="radar-note">These are estimates from individual statistics. Chemistry, coaching and fatigue are not modelled.</p>
        </>
      )}
    </>
  );
}
