import { useMemo, useState } from 'react';
import type { CSSProperties, DragEvent, FormEvent } from 'react';
import { useApp } from '../AppContext';
import { formatStat, POSITIONS, statByKey } from '../stats';
import { teamVars } from '../teamColors';
import type { FormRow, PlayerDirectoryRow, PlayerScore, ScoutNote } from '../types';
import { useApi } from '../useApi';
import { usePersisted } from '../usePersisted';
import { Avatar } from './Avatar';
import { PageHead, Segmented, TeamLogo } from './Common';
import { Dropdown } from './Dropdown';
import { CloseIcon, CompareIcon } from './Icons';
import { Pagination, usePaged } from './Pagination';

type Props = {
  favoritePlayers: PlayerDirectoryRow[];
  groups: Record<string, number[]>;
  setGroups: (updater: (current: Record<string, number[]>) => Record<string, number[]>) => void;
  notes: Record<number, ScoutNote>;
  setNote: (playerId: number, note: Partial<ScoutNote>) => void;
  onToggleFavorite: (playerId: number) => void;
};

const STATUSES = ['Watching', 'Scouted', 'Target', 'Not now'];
const EMPTY: ScoutNote = { text: '', stars: 0, status: '' };
const LINE = ['points', 'rebounds', 'assists', 'ts'];
const SORTS = [{ value: 'saved', label: 'Newest first' }, { value: 'stars', label: 'My rating' }, { value: 'score', label: 'Overall score' }, { value: 'form', label: 'Best form' }, { value: 'points', label: 'Points' }, { value: 'age', label: 'Youngest' }];
const mainPosition = (p: PlayerDirectoryRow) => (p.position ?? '').split('-')[0];

function Stars({ value, onChange, name }: { value: number; onChange: (v: number) => void; name: string }) {
  const [hover, setHover] = useState(0);
  return <span className="stars" role="group" aria-label={`Rating for ${name}`} onMouseLeave={() => setHover(0)}>{[1, 2, 3, 4, 5].map((n) => <button type="button" key={n} className={n <= (hover || value) ? 'on' : ''} aria-label={`${n} of 5`} aria-pressed={value === n} onMouseEnter={() => setHover(n)} onClick={() => onChange(value === n ? 0 : n)}>★</button>)}</span>;
}

/** Half a court with the shortlist's players placed by position. */
function Depth({ players, onOpen }: { players: PlayerDirectoryRow[]; onOpen: (id: number) => void }) {
  const at: Record<string, [number, number]> = { Guard: [50, 80], Forward: [50, 49], Center: [50, 19] };
  return (
    <div className="depth" aria-label="Shortlist by position">
      <svg viewBox="0 0 500 420" preserveAspectRatio="none" aria-hidden="true"><g className="court-lines" fill="none"><rect x={2} y={2} width={496} height={416} /><rect x={170} y={2} width={160} height={150} /><path d="M190 152A60 60 0 0 0 310 152" /><path d="M30 2V100A237 237 0 0 0 470 100V2" /><circle cx={250} cy={42} r={8} className="court-hoop" /></g></svg>
      {POSITIONS.map((name) => {
        const own = players.filter((p) => mainPosition(p) === name);
        return <div className="depth-row" key={name} style={{ left: `${at[name][0]}%`, top: `${at[name][1]}%` }}><small>{name}s {own.length}</small><div>{own.slice(0, 6).map((p) => <button type="button" key={p.player_id} title={p.full_name} aria-label={p.full_name} style={teamVars(p.club_team_id)} onClick={() => onOpen(p.player_id)}><Avatar key={p.nba_player_id} name={p.full_name} nbaPlayerId={p.nba_player_id} className="player-thumb" /></button>)}{own.length > 6 && <em>+{own.length - 6}</em>}{!own.length && <em className="gap-mark">nobody yet</em>}</div></div>;
      })}
    </div>
  );
}

export function Shortlist({ favoritePlayers, groups, setGroups, notes, setNote, onToggleFavorite }: Props) {
  const { totals, open, go, browse, setCompareIds, user } = useApp();
  const scores = useApi<PlayerScore[]>('/insights/scores');
  const form = useApi<FormRow[]>('/form?games=10');
  const [view, setView] = usePersisted<'cards' | 'board'>('short-view', 'cards');
  const [sort, setSort] = usePersisted('short-sort', 'saved');
  const [status, setStatus] = usePersisted('short-status', '');
  const [picked, setPicked] = useState<number[]>([]);
  const [newGroup, setNewGroup] = useState('');
  const [dragging, setDragging] = useState<number | null>(null);
  const [over, setOver] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const scoreOf = useMemo(() => new Map((scores.data ?? []).map((s) => [s.player_id, s])), [scores.data]);
  const formOf = useMemo(() => new Map((form.data ?? []).map((f) => [f.player_id, f])), [form.data]);
  const note = (id: number) => notes[id] ?? EMPTY;
  const groupNames = Object.keys(groups);
  const groupOf = (id: number) => groupNames.find((n) => groups[n].includes(id)) ?? '';
  const age = (p: PlayerDirectoryRow) => statByKey('age').get(p, totals[p.player_id]);
  const swing = (id: number) => { const s = formOf.get(id)?.stats.points; return s ? s.now - s.before : 0; };

  const shown = favoritePlayers.filter((p) => !status || (status === 'none' ? !note(p.player_id).status : note(p.player_id).status === status));
  const sorted = [...shown].sort((a, b) => sort === 'stars' ? note(b.player_id).stars - note(a.player_id).stars : sort === 'score' ? (scoreOf.get(b.player_id)?.score ?? 0) - (scoreOf.get(a.player_id)?.score ?? 0) : sort === 'form' ? swing(b.player_id) - swing(a.player_id) : sort === 'points' ? (b.points ?? 0) - (a.points ?? 0) : sort === 'age' ? (age(a) ?? 99) - (age(b) ?? 99) : 0);
  const paged = usePaged(sorted, 12, `${sort}${status}${favoritePlayers.length}`);
  const average = (values: (number | null | undefined)[]) => { const list = values.filter((v): v is number => v != null); return list.length ? list.reduce((s, v) => s + v, 0) / list.length : null; };

  /** A player belongs to at most one group; an empty name takes them out. */
  const assign = (id: number, name: string) => setGroups((current) => {
    const next = Object.fromEntries(Object.entries(current).map(([k, ids]) => [k, ids.filter((v) => v !== id)]));
    if (name) next[name] = [...(next[name] ?? []), id];
    return next;
  });
  const createGroup = (e: FormEvent) => {
    e.preventDefault();
    const name = newGroup.trim();
    if (!name || groups[name]) return;
    setGroups((current) => ({ ...current, [name]: [] }));
    setNewGroup('');
  };
  const removeGroup = (name: string) => { setGroups((current) => Object.fromEntries(Object.entries(current).filter(([k]) => k !== name))); setConfirming(null); };
  const add = () => browse({ title: 'Add players to the shortlist', max: 12, min: 1, confirm: 'Add to shortlist', exclude: favoritePlayers.map((p) => p.player_id), onDone: (ids) => ids.forEach(onToggleFavorite) });
  const tick = (id: number) => setPicked((ids) => (ids.includes(id) ? ids.filter((v) => v !== id) : ids.length >= 6 ? ids : [...ids, id]));
  const chosen = picked.filter((id) => favoritePlayers.some((p) => p.player_id === id));

  if (!favoritePlayers.length) {
    return (
      <>
        <PageHead title="Scouting board" intro="Players you follow, your notes on them and where they would fit." />
        <div className="empty-board"><Depth players={[]} onOpen={open} /><div><h2>Nobody on the board yet</h2><p>Tap the heart next to any player, or pick a few from the list. You can rate them, write notes, and sort them into groups such as “Sixth man” or “Rim protector”.</p><button type="button" className="submit-button" onClick={add}>Add players</button></div></div>
      </>
    );
  }

  const trend = (id: number) => {
    const f = formOf.get(id)?.stats.points;
    if (!f) return null;
    const games = f.games.map((v) => v ?? 0), top = Math.max(1, ...games), delta = f.now - f.before;
    return <span className={`board-form ${delta >= 2 ? 'up' : delta <= -2 ? 'down' : ''}`} title={`Points in the last ${games.length} games`}><span>{games.map((v, i) => <i key={i} style={{ height: `${Math.max(8, (v / top) * 100)}%` }} />)}</span><b>{delta >= 2 ? '▲' : delta <= -2 ? '▼' : '●'} {Math.abs(delta).toFixed(1)}</b></span>;
  };
  const card = (p: PlayerDirectoryRow) => {
    const n = note(p.player_id), s = scoreOf.get(p.player_id);
    return (
      <article className={`board-card team-tint ${chosen.includes(p.player_id) ? 'picked' : ''}`} key={p.player_id} style={teamVars(p.club_team_id)}>
        <span className="board-logo"><TeamLogo teamId={p.club_team_id} size={190} /></span>
        <div className="board-top">
          <button type="button" className="board-photo" aria-label={`Open ${p.full_name}`} onClick={() => open(p.player_id)}><Avatar key={p.nba_player_id} name={p.full_name} nbaPlayerId={p.nba_player_id} className="podium-photo" /></button>
          {s && <span className="board-score" style={{ '--share': s.score / 100 } as CSSProperties} title={`Overall ${s.score}, offense ${s.offense}, defense ${s.defense}, out of 100`}><b>{s.score}</b></span>}
          <button type="button" className="icon-button small" aria-label={`Remove ${p.full_name} from the shortlist`} title="Remove" onClick={() => onToggleFavorite(p.player_id)}><CloseIcon /></button>
        </div>
        <div className="board-name"><button type="button" className="player-link" onClick={() => open(p.player_id)}>{p.full_name}</button><small>{[p.club, p.position, age(p) != null && `${age(p)} years`].filter(Boolean).join(', ')}</small></div>
        <dl className="board-line">{LINE.map((k) => <div key={k}><dd>{formatStat(statByKey(k), statByKey(k).get(p, totals[p.player_id]))}</dd><dt>{statByKey(k).short}</dt></div>)}</dl>
        <div className="board-mid"><Stars value={n.stars} name={p.full_name} onChange={(stars) => setNote(p.player_id, { stars })} />{trend(p.player_id)}</div>
        <div className="board-status" role="group" aria-label={`Status of ${p.full_name}`}>{STATUSES.map((x) => <button type="button" key={x} aria-pressed={n.status === x} onClick={() => setNote(p.player_id, { status: n.status === x ? '' : x })}>{x}</button>)}</div>
        <textarea className="board-note" rows={2} maxLength={600} placeholder="Write a note…" aria-label={`Note on ${p.full_name}`} value={n.text} onChange={(e) => setNote(p.player_id, { text: e.target.value })} />
        <div className="board-foot">
          <Dropdown label={`Group for ${p.full_name}`} value={groupOf(p.player_id)} options={[{ value: '', label: 'No group' }, ...groupNames.map((g) => ({ value: g, label: g }))]} onChange={(g) => assign(p.player_id, g)} />
          <button type="button" className={`ghost-button ${chosen.includes(p.player_id) ? 'on' : ''}`} aria-pressed={chosen.includes(p.player_id)} onClick={() => tick(p.player_id)}><CompareIcon />Compare</button>
        </div>
      </article>
    );
  };
  const drop = (name: string) => ({
    onDragOver: (e: DragEvent) => { if (dragging != null) { e.preventDefault(); setOver(name); } },
    onDragLeave: () => setOver((current) => (current === name ? null : current)),
    onDrop: (e: DragEvent) => { e.preventDefault(); if (dragging != null) assign(dragging, name); setDragging(null); setOver(null); },
  });
  const column = (name: string, title: string, people: PlayerDirectoryRow[]) => (
    <section key={title} className={`board-column ${over === name ? 'over' : ''}`} {...drop(name)}>
      <header><b>{title}</b><span>{people.length}</span>{name && (confirming === name ? <><button type="button" className="link-button" onClick={() => removeGroup(name)}>Delete</button><button type="button" className="link-button quiet" onClick={() => setConfirming(null)}>Keep</button></> : <button type="button" className="icon-button small" aria-label={`Delete the group ${name}`} title="Delete group" onClick={() => setConfirming(name)}><CloseIcon /></button>)}</header>
      {people.length > 0 && <p className="board-sum">{average(people.map((p) => p.points))?.toFixed(1)} pts, {average(people.map((p) => p.rebounds))?.toFixed(1)} reb, {average(people.map((p) => p.assists))?.toFixed(1)} ast, age {average(people.map(age))?.toFixed(1)}</p>}
      {people.map((p) => {
        const n = note(p.player_id);
        return (
          <div key={p.player_id} className={`board-item team-tint ${dragging === p.player_id ? 'moving' : ''}`} style={teamVars(p.club_team_id)} draggable onDragStart={(e) => { e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', String(p.player_id)); setDragging(p.player_id); }} onDragEnd={() => { setDragging(null); setOver(null); }}>
            <Avatar key={p.nba_player_id} name={p.full_name} nbaPlayerId={p.nba_player_id} className="recent-photo" />
            <span><button type="button" className="player-link" onClick={() => open(p.player_id)}>{p.full_name}</button><small>{p.club}, {p.position}</small>{n.stars > 0 && <small className="board-stars">{'★'.repeat(n.stars)}</small>}{n.status && <small className="board-tag">{n.status}</small>}</span>
            <Dropdown label={`Move ${p.full_name}`} value={groupOf(p.player_id)} options={[{ value: '', label: 'No group' }, ...groupNames.map((g) => ({ value: g, label: g }))]} onChange={(g) => assign(p.player_id, g)} />
          </div>
        );
      })}
      {!people.length && <p className="board-empty">Drag a player here</p>}
    </section>
  );
  const counts = POSITIONS.map((name) => ({ name, n: favoritePlayers.filter((p) => mainPosition(p) === name).length }));
  const thin = [...counts].sort((a, b) => a.n - b.n)[0];
  const overall = average(favoritePlayers.map((p) => scoreOf.get(p.player_id)?.score));
  const hottest = [...favoritePlayers].sort((a, b) => swing(b.player_id) - swing(a.player_id))[0];
  const topRated = [...favoritePlayers].sort((a, b) => (scoreOf.get(b.player_id)?.score ?? 0) - (scoreOf.get(a.player_id)?.score ?? 0))[0];
  return (
    <>
      <PageHead title="Scouting board" intro={user ? 'Saved to your account: ratings, notes and groups.' : 'Saved in this browser. Sign in to keep it everywhere.'}><button type="button" className="submit-button" onClick={add}>Add players</button></PageHead>
      <section className="board-hero">
        <Depth players={favoritePlayers} onOpen={open} />
        <div className="board-facts">
          <div className="board-big"><strong>{favoritePlayers.length}</strong><span>{favoritePlayers.length === 1 ? 'player' : 'players'} on the board</span></div>
          <dl>
            <div><dt>Average overall score</dt><dd>{overall == null ? '–' : overall.toFixed(0)}<small>of 100</small></dd></div>
            <div><dt>Average age</dt><dd>{average(favoritePlayers.map(age))?.toFixed(1) ?? '–'}</dd></div>
            <div><dt>Average scoring</dt><dd>{average(favoritePlayers.map((p) => p.points))?.toFixed(1)} pts</dd></div>
            {topRated && scoreOf.size > 0 && <div><dt>Highest score</dt><dd><button type="button" className="player-link" onClick={() => open(topRated.player_id)}>{topRated.full_name}</button></dd></div>}
            {hottest && swing(hottest.player_id) > 0 && <div><dt>Hottest, last 10</dt><dd><button type="button" className="player-link" onClick={() => open(hottest.player_id)}>{hottest.full_name}</button><small>+{swing(hottest.player_id).toFixed(1)} pts</small></dd></div>}
            <div><dt>Thinnest position</dt><dd>{thin.name}<small>{thin.n} {thin.n === 1 ? 'player' : 'players'}</small></dd></div>
          </dl>
        </div>
      </section>
      <div className="filter-bar board-tools">
        <Segmented label="View" value={view} options={[['cards', 'Cards'], ['board', 'Groups']]} onChange={setView} />
        {view === 'cards' && <><Dropdown label="Sort" value={sort} options={SORTS} onChange={setSort} /><Segmented label="Status" value={status} options={[['', 'All'], ...STATUSES.map((s) => [s, `${s} ${favoritePlayers.filter((p) => note(p.player_id).status === s).length}`] as [string, string]), ['none', 'No status']]} onChange={setStatus} /></>}
        {view === 'board' && <form className="group-create" onSubmit={createGroup}><input className="control-input" maxLength={60} aria-label="New group name" value={newGroup} onChange={(e) => setNewGroup(e.target.value)} placeholder="New group, e.g. Sixth man" /><button className="nav-button" type="submit" disabled={!newGroup.trim() || Boolean(groups[newGroup.trim()])}>Create group</button></form>}
      </div>
      {view === 'cards' ? (
        <>
          {sorted.length ? <div className="board-grid">{paged.items.map(card)}</div> : <div className="empty-state"><p>No players with this status.</p></div>}
          <Pagination page={paged.page} pageCount={paged.pageCount} onPage={(n) => { paged.onPage(n); window.scrollTo({ top: 0 }); }} label="Shortlist pages" />
        </>
      ) : <div className="board-columns">{column('', 'No group', favoritePlayers.filter((p) => !groupOf(p.player_id)))}{groupNames.map((name) => column(name, name, favoritePlayers.filter((p) => groups[name].includes(p.player_id))))}</div>}
      {chosen.length > 0 && <div className="board-tray"><span>{chosen.length} chosen</span>{chosen.map((id) => { const p = favoritePlayers.find((x) => x.player_id === id)!; return <button type="button" className="tray-chip" key={id} onClick={() => tick(id)}>{p.full_name}<CloseIcon /></button>; })}<button type="button" className="submit-button" disabled={chosen.length < 2} onClick={() => { setCompareIds(chosen); go('compare'); }}>{chosen.length < 2 ? 'Choose one more' : 'Compare'}</button></div>}
    </>
  );
}
