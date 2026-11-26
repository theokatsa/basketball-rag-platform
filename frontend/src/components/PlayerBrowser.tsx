import { useEffect, useMemo, useRef, useState } from 'react';
import { useApp } from '../AppContext';
import type { BrowseRequest } from '../AppContext';
import { formatStat, playsPosition, POSITIONS, qualifies, SERIES, statByKey } from '../stats';
import type { SimilarPlayerResult } from '../types';
import { useApi } from '../useApi';
import { plain } from '../utils';
import { Avatar } from './Avatar';
import { Segmented, TeamLogo } from './Common';
import { StatSelect, TeamSelect } from './Dropdown';
import { CloseIcon, SearchIcon } from './Icons';
import { Pagination, usePaged } from './Pagination';

type Source = 'all' | 'similar' | 'recent' | 'shortlist';
const ROWS = 8;

/** The player list used everywhere a player has to be chosen. */
export function PlayerBrowser({ request, onClose }: { request: BrowseRequest; onClose: () => void }) {
  const { players, totals, byId, favoriteIds, historyIds, user } = useApp();
  const { title, max, min = 1, exclude = [] } = request;
  const [chosen, setChosen] = useState<number[]>(request.selected ?? []);
  const [query, setQuery] = useState('');
  const [club, setClub] = useState('');
  const [position, setPosition] = useState(request.position ?? '');
  const [sort, setSort] = useState('points');
  const [source, setSource] = useState<Source>('all');
  const dialog = useRef<HTMLDialogElement>(null);
  const anchor = chosen[0] ?? null;
  const similar = useApi<SimilarPlayerResult[]>(source === 'similar' && anchor != null ? `/players/${anchor}/similar?limit=25` : null);

  useEffect(() => {
    const element = dialog.current;
    if (element && !element.open) element.showModal();
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = ''; };
  }, []);

  const stat = statByKey(sort);
  const rows = useMemo(() => {
    const term = plain(query.trim());
    const order = source === 'similar' ? (similar.data ?? []).map((s) => s.player_id) : source === 'recent' ? historyIds : source === 'shortlist' ? favoriteIds : null;
    const base = order ? order.map((id) => byId.get(id)).filter((p) => p != null) : players;
    const found = base.filter((p) => !exclude.includes(p.player_id) && (!term || plain(p.full_name).includes(term)) && (!club || p.club_full_name === club) && playsPosition(p, position) && (source !== 'similar' || p.player_id !== anchor));
    if (order) return found;
    const sign = stat.lowerIsBetter ? 1 : -1;
    const value = (p: (typeof found)[number]) => { const t = totals[p.player_id]; return qualifies(stat, t) ? stat.get(p, t) : null; };
    return found.map((p) => ({ p, v: value(p) })).sort((a, b) => (a.v == null || b.v == null ? (a.v == null ? 1 : 0) - (b.v == null ? 1 : 0) : sign * (a.v - b.v))).map((r) => r.p);
  }, [players, totals, byId, query, club, position, stat, source, similar.data, historyIds, favoriteIds, exclude, anchor]);
  const paged = usePaged(rows, ROWS, [query, club, position, sort, source].join('|'));

  const finish = (ids: number[]) => { onClose(); request.onDone(ids); };
  const toggle = (id: number) => {
    if (max === 1) finish([id]);
    else setChosen((list) => (list.includes(id) ? list.filter((v) => v !== id) : list.length >= max ? list : [...list, id]));
  };
  const sources: [Source, string][] = [['all', 'All players'], ...(anchor != null && max > 1 ? [['similar', 'Similar'] as [Source, string]] : []), ...(historyIds.length ? [['recent', 'Recent'] as [Source, string]] : []), ...(user && favoriteIds.length ? [['shortlist', 'Shortlist'] as [Source, string]] : [])];
  const columns = [...new Set(['points', 'rebounds', 'assists', sort])].map(statByKey);

  return (
    <dialog className="browser" ref={dialog} aria-label={title} onCancel={(e) => { e.preventDefault(); onClose(); }} onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="browser-box">
        <header><h2>{title}</h2><button type="button" className="icon-button" aria-label="Close" onClick={onClose}><CloseIcon /></button></header>
        <div className="browser-tools">
          <div className="search-field"><SearchIcon /><input autoFocus className="control-input" placeholder="Search by name" aria-label="Search by name" value={query} onChange={(e) => setQuery(e.target.value)} /></div>
          <TeamSelect value={club} onChange={setClub} />
          <StatSelect label="Sort by" value={sort} onChange={setSort} />
        </div>
        <div className="browser-tools second">
          {sources.length > 1 && <Segmented label="Which players" value={source} options={sources} onChange={setSource} />}
          <Segmented label="Position" value={position} options={[['', 'Any position'], ...POSITIONS.map((p) => [p, `${p}s`] as [string, string])]} onChange={setPosition} />
        </div>
        <ul className="browser-list">
          {paged.items.map((p) => {
            const on = chosen.includes(p.player_id);
            return (
              <li key={p.player_id}>
                <button type="button" className={on ? 'on' : ''} aria-pressed={max > 1 ? on : undefined} disabled={max > 1 && !on && chosen.length >= max} onClick={() => toggle(p.player_id)}>
                  {max > 1 && <i className="tick" aria-hidden="true" style={on ? { background: SERIES[chosen.indexOf(p.player_id) % SERIES.length] } : undefined}>{on ? '✓' : ''}</i>}
                  <Avatar key={p.nba_player_id} name={p.full_name} nbaPlayerId={p.nba_player_id} className="player-thumb" />
                  <span className="browser-name"><b>{p.full_name}</b><small>{p.position}</small></span>
                  <TeamLogo teamId={p.club_team_id} size={26} />
                  {columns.map((s) => <span className={`browser-stat ${s.key === sort ? 'main' : ''}`} key={s.key}><b>{formatStat(s, s.get(p, totals[p.player_id]))}</b><small>{s.short}</small></span>)}
                </button>
              </li>
            );
          })}
          {!paged.items.length && <li className="none">{source === 'similar' && !similar.data && !similar.error ? 'Finding similar players…' : 'No player matches.'}</li>}
        </ul>
        <Pagination page={paged.page} pageCount={paged.pageCount} onPage={paged.onPage} label="Player list pages" />
        {max > 1 && (
          <footer>
            <div className="chosen-row">
              {chosen.map((id, i) => { const p = byId.get(id); return p && <button type="button" key={id} className="chosen-chip" style={{ borderColor: SERIES[i % SERIES.length] }} onClick={() => toggle(id)} aria-label={`Remove ${p.full_name}`}><Avatar key={p.nba_player_id} name={p.full_name} nbaPlayerId={p.nba_player_id} className="player-thumb" />{p.full_name}<CloseIcon /></button>; })}
              <small>{chosen.length} of {max} chosen</small>
            </div>
            <button type="button" className="submit-button" disabled={chosen.length < min} onClick={() => finish(chosen)}>{chosen.length < min ? `Pick ${min - chosen.length} more` : request.confirm ?? 'Done'}</button>
          </footer>
        )}
      </div>
    </dialog>
  );
}
