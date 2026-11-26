import { useState } from 'react';
import { useApp } from '../AppContext';
import { Avatar } from './Avatar';
import { PlayerCell } from './Common';
import { signed } from './CourtZones';
import { SERIES } from '../stats';
import type { LineupResult } from '../types';

type Stat = LineupResult['stats'][number];
const GROUPS: [string, RegExp][] = [['Shooting', /shooting|three|free throw/i], ['Playmaking', /assist|turnover/i], ['Rebounding', /rebound/i], ['Defense', /steal|block|contest/i]];
const groupOf = (s: Stat) => GROUPS.find(([, re]) => re.test(s.label))?.[0] ?? 'Other';

function verdict(net: number): string {
  if (net >= 6) return 'Elite on paper';
  if (net >= 2.5) return 'Strong';
  if (net > -2.5) return 'About average';
  if (net > -6) return 'Below average';
  return 'Struggles on paper';
}

/** A bar from -15 to +15 with the lineup's mark. */
function Gauge({ value }: { value: number }) {
  const at = Math.max(0, Math.min(100, ((value + 15) / 30) * 100));
  return (
    <div className="lu-gauge" role="img" aria-label={`Net rating ${signed(value)} on a scale from -15 to +15`}>
      <i><em style={{ left: `${at}%` }} className={value >= 0 ? 'up' : 'down'} /></i>
      <span><small>-15</small><small>0</small><small>+15</small></span>
    </div>
  );
}

function Scoreboard({ data, name }: { data: LineupResult; name: (id: number) => string }) {
  const ups = data.stats.filter((s) => s.z >= 1).sort((a, b) => b.z - a.z), downs = data.stats.filter((s) => s.z <= -1).sort((a, b) => a.z - b.z);
  const side = (label: string, value: number, better: number) => (
    <div className="lu-side">
      <small>{label}</small>
      <strong className={better > 1 ? 'up' : better < -1 ? 'down' : ''}>{value.toFixed(1)}</strong>
      <span>{Math.abs(better).toFixed(1)} {better >= 0 ? 'better' : 'worse'} than average</span>
    </div>
  );
  const tag = (s: Stat, cls: string) => <span key={s.label} className={cls} title={s.note}>{s.label}<b>{signed(s.own - s.base)}</b></span>;
  return (
    <section className="panel lu-score">
      <div className="lu-score-top">
        <div className={`lu-net ${data.net >= 0 ? 'up' : 'down'}`}>
          <small>Net rating</small>
          <strong>{signed(data.net)}</strong>
          <b>{verdict(data.net)}</b>
          <Gauge value={data.net} />
        </div>
        {side('Offense', data.offense, data.offense - data.league)}
        {side('Defense', data.defense, data.league - data.defense)}
        <div className="lu-side">
          <small>Average height</small>
          <strong>{data.average_height ? <>{Math.floor(data.average_height / 12)}&apos;{(data.average_height % 12).toFixed(1)}&quot;</> : '–'}</strong>
          <span>{data.average_height ? `${Math.round(data.average_height * 2.54)} cm` : 'Not known'}</span>
        </div>
        <div className="lu-checks">
          {data.checks.map((c) => { const ok = c.players.length >= c.target; return (
            <div key={c.label} className={ok ? 'ok' : 'short'} title={c.players.map(name).join(', ') || c.note}>
              <span className="balance-mark" aria-hidden="true">{ok ? '✓' : '!'}</span>
              <span><b>{c.label}</b><small>{c.players.length} of {c.target} {ok ? '' : '· short'}</small></span>
            </div>
          ); })}
        </div>
      </div>
      <div className="lu-tags">
        <div><h3>Strengths</h3>{ups.length ? <div className="verdict-tags">{ups.map((s) => tag(s, 'up'))}</div> : <p className="count-label">Nothing clearly above average.</p>}</div>
        <div><h3>Weak points</h3>{downs.length ? <div className="verdict-tags">{downs.map((s) => tag(s, 'down'))}</div> : <p className="count-label">Nothing clearly below average.</p>}</div>
      </div>
      <p className="lu-foot">Offense and defense are points per 100 possessions; the league average is {data.league.toFixed(1)}.</p>
    </section>
  );
}

function Profile({ stats }: { stats: Stat[] }) {
  const groups = [...GROUPS.map(([g]) => g), 'Other'].map((g) => [g, stats.filter((s) => groupOf(s) === g)] as const).filter(([, list]) => list.length);
  return (
    <section className="panel">
      <div className="panel-header"><div><h2>Against an average five</h2><p>The centre line is an average lineup. Orange is better, blue is worse.</p></div></div>
      <div className="lu-profile">
        {groups.map(([g, list]) => (
          <div key={g} className="lu-group">
            <h3>{g}</h3>
            {list.map((s) => (
              <div key={s.label} className="lu-row">
                <span className="lu-label">{s.label}{s.note && <small>{s.note}</small>}</span>
                <i className="lu-bar"><em className={s.z >= 0 ? 'up' : 'down'} style={s.z >= 0 ? { left: '50%', width: `${Math.min(50, s.z * 12.5)}%` } : { right: '50%', width: `${Math.min(50, -s.z * 12.5)}%` }} /></i>
                <b>{s.own.toFixed(1)}</b>
                <small>avg {s.base.toFixed(1)}</small>
              </div>
            ))}
          </div>
        ))}
      </div>
    </section>
  );
}

function Usage({ data, order }: { data: LineupResult; order: number[] }) {
  const { byId } = useApp();
  const shares = [...data.shares].sort((a, b) => order.indexOf(a.player_id) - order.indexOf(b.player_id));
  const top = Math.max(35, ...shares.map((s) => Math.max(s.own, s.in_lineup)));
  return (
    <section className="panel">
      <div className="panel-header"><div><h2>Who gets the ball</h2><p>Usual shares add up to {data.total_usage.toFixed(0)}%, so they are scaled to 100. {data.total_usage > 100 ? 'Giving up shots makes players a little more efficient.' : 'Taking on more shots makes players a little less efficient.'}</p></div></div>
      <div className="share-bar" role="img" aria-label={shares.map((s) => `${byId.get(s.player_id)?.full_name ?? ''} ${s.in_lineup.toFixed(0)}%`).join(', ')}>{shares.map((s, i) => <i key={s.player_id} style={{ width: `${s.in_lineup}%`, background: SERIES[i] }} title={`${byId.get(s.player_id)?.full_name}: ${s.in_lineup.toFixed(0)}%`} />)}</div>
      <div className="lu-usage">
        {shares.map((s, i) => { const p = byId.get(s.player_id); return p && (
          <div key={s.player_id} className="lu-usage-row">
            <i className="lu-swatch" style={{ background: SERIES[i] }} />
            <PlayerCell player={p} note={`${s.points_per_100.toFixed(0)} pts per 100 uses (${signed(s.points_per_100 - s.own_points_per_100)})`} />
            <span className="lu-share" title={`${s.own.toFixed(0)}% of plays usually, ${s.in_lineup.toFixed(0)}% in this lineup`}>
              <i><em style={{ width: `${(s.in_lineup / top) * 100}%`, background: SERIES[i] }} /><u style={{ left: `${(s.own / top) * 100}%` }} /></i>
              <small><b>{s.in_lineup.toFixed(0)}%</b> here, {s.own.toFixed(0)}% usually</small>
            </span>
          </div>
        ); })}
      </div>
      <p className="lu-foot">The white tick is the player&apos;s usual share.</p>
    </section>
  );
}

function Chemistry({ data, order }: { data: LineupResult; order: number[] }) {
  const { byId } = useApp();
  const pair = (a: number, b: number) => data.pairs.find((x) => (x.player_a === a && x.player_b === b) || (x.player_a === b && x.player_b === a));
  const last = (id: number) => { const n = byId.get(id)?.full_name ?? ''; return n.split(' ').slice(1).join(' ') || n; };
  const shade = (net: number) => { const a = Math.min(0.85, 0.18 + Math.abs(net) / 14); return net >= 0 ? `rgba(255, 106, 19, ${a})` : `rgba(57, 135, 229, ${a})`; };
  return (
    <section className="panel">
      <div className="panel-header"><div><h2>Chemistry</h2><p>Real net rating of each pair with both on the court in 2024-25</p></div></div>
      <div className="lu-matrix" style={{ gridTemplateColumns: `minmax(5.5rem, auto) repeat(${order.length}, minmax(0, 1fr))` }}>
        <span />
        {order.map((id) => { const p = byId.get(id); return p && <span key={id} className="lu-mx-head" title={p.full_name}><Avatar key={p.nba_player_id} name={p.full_name} nbaPlayerId={p.nba_player_id} className="player-thumb" /></span>; })}
        {order.map((row) => (
          <div key={row} className="lu-mx-row">
            <span className="lu-mx-name" title={byId.get(row)?.full_name}>{last(row)}</span>
            {order.map((col) => {
              if (row === col) return <span key={col} className="lu-mx-cell self" />;
              const x = pair(row, col);
              return x
                ? <span key={col} className="lu-mx-cell" style={{ background: shade(x.net_rating) }} title={`${byId.get(row)?.full_name} and ${byId.get(col)?.full_name}: ${signed(x.net_rating)} in ${x.minutes.toFixed(0)} minutes`}><b>{signed(x.net_rating)}</b><small>{x.minutes.toFixed(0)}m</small></span>
                : <span key={col} className="lu-mx-cell none" title="Never on the court together">–</span>;
            })}
          </div>
        ))}
      </div>
      {!data.pairs.length && <p className="lu-foot">None of these players shared the court in 2024-25.</p>}
    </section>
  );
}

function Matchups({ data, order }: { data: LineupResult; order: number[] }) {
  const { byId, open } = useApp();
  const [shown, setShown] = useState<number | null>(null);
  const rows = [...data.opponents].sort((a, b) => order.indexOf(a.player_id) - order.indexOf(b.player_id));
  const face = (x: { player_id: number; notes: string[] }) => {
    const r = byId.get(x.player_id);
    return r && (
      <button type="button" key={x.player_id} className="lu-opp" onClick={() => open(r.player_id)}>
        <Avatar key={r.nba_player_id} name={r.full_name} nbaPlayerId={r.nba_player_id} className="player-thumb" />
        <span><b>{r.full_name}</b><small>{r.club} · {(x.notes[0] ?? r.position ?? '').replace(/Offense (\d+), defense (\d+) out of 100/, 'Off $1 · Def $2')}</small></span>
      </button>
    );
  };
  return (
    <section className="panel">
      <div className="panel-header"><div><h2>Opponents, position by position</h2><p>Players at the same position, from overall statistics, size and real matchups where they exist. Ratings are percentiles, 0 to 100.</p></div></div>
      <div className="lu-opps">
        <div className="lu-opps-head"><span>Your player</span><span>Hardest to face</span><span>Best to face</span><span /></div>
        {rows.map((o) => { const p = byId.get(o.player_id); const open_ = shown === o.player_id; return p && (
          <div key={o.player_id} className="lu-opps-row">
            <PlayerCell player={p} />
            <div className="lu-opp-list hard" data-label="Hardest to face">{o.toughest.map(face)}</div>
            <div className="lu-opp-list easy" data-label="Best to face">{o.easiest.map(face)}</div>
            <button type="button" className="text-button" aria-expanded={open_} onClick={() => setShown(open_ ? null : o.player_id)}>{open_ ? 'Hide' : 'Why'}</button>
            {open_ && (
              <div className="lu-why">
                {[...o.toughest, ...o.easiest].map((x) => <p key={x.player_id}><b>{byId.get(x.player_id)?.full_name}:</b> {x.notes.join('. ')}.</p>)}
              </div>
            )}
          </div>
        ); })}
      </div>
      <p className="lu-foot">Planned: replace these rules with a model trained on lineup results, so it can learn which players win their matchups.</p>
    </section>
  );
}

export function LineupReport({ data, order }: { data: LineupResult; order: number[] }) {
  const { byId } = useApp();
  const name = (id: number) => byId.get(id)?.full_name ?? '';
  return (
    <div className="lu-report">
      <Scoreboard data={data} name={name} />
      <div className="lu-cols">
        <Profile stats={data.stats} />
        <div className="lu-stack">
          <Usage data={data} order={order} />
          <Chemistry data={data} order={order} />
        </div>
      </div>
      <Matchups data={data} order={order} />
      <p className="radar-note">These are estimates from individual statistics. Chemistry, coaching and fatigue are not modelled.</p>
    </div>
  );
}
