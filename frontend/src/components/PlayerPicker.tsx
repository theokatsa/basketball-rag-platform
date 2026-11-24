import { useId, useMemo, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { useApp } from '../AppContext';
import { plain } from '../utils';
import { Avatar } from './Avatar';
import { SearchIcon } from './Icons';

type Props = { label: string; placeholder?: string; exclude?: number[]; onPick: (playerId: number) => void };

/** Type-ahead player search: arrow keys, Enter and Escape work. */
export function PlayerPicker({ label, placeholder = 'Type a player name', exclude = [], onPick }: Props) {
  const { players, loading } = useApp();
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const [open, setOpen] = useState(false);
  const listId = useId();
  const matches = useMemo(() => {
    const term = plain(query.trim());
    if (!term) return [];
    return players.filter((p) => !exclude.includes(p.player_id) && plain(p.full_name).includes(term)).sort((a, b) => (b.points ?? 0) - (a.points ?? 0)).slice(0, 7);
  }, [players, query, exclude]);
  const show = open && query.trim().length > 0;
  const pick = (id: number) => { onPick(id); setQuery(''); setOpen(false); };
  const onKey = (event: KeyboardEvent) => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (matches.length) setActive((i) => (i + (event.key === 'ArrowDown' ? 1 : -1) + matches.length) % matches.length);
    } else if (event.key === 'Enter') {
      event.preventDefault();
      if (matches[active]) pick(matches[active].player_id);
    } else if (event.key === 'Escape') setOpen(false);
  };
  return (
    <div className="picker">
      <div className="search-field">
        <SearchIcon />
        <input className="control-input" role="combobox" aria-label={label} aria-expanded={show} aria-controls={listId} aria-autocomplete="list" aria-activedescendant={show && matches[active] ? `${listId}-${active}` : undefined} placeholder={placeholder} value={query} onChange={(e) => { setQuery(e.target.value); setActive(0); setOpen(true); }} onFocus={() => setOpen(true)} onBlur={() => setOpen(false)} onKeyDown={onKey} />
      </div>
      {show && (
        <ul className="picker-list" id={listId} role="listbox">
          {matches.map((p, i) => (
            <li key={p.player_id} id={`${listId}-${i}`} role="option" aria-selected={i === active} className={i === active ? 'active' : ''} onMouseEnter={() => setActive(i)} onMouseDown={(e) => { e.preventDefault(); pick(p.player_id); }}>
              <Avatar name={p.full_name} nbaPlayerId={p.nba_player_id} className="player-thumb" /><span>{p.full_name}</span><small>{p.club} {p.points?.toFixed(1)} pts</small>
            </li>
          ))}
          {!matches.length && <li className="none">{loading ? 'Loading players…' : 'No player found'}</li>}
        </ul>
      )}
    </div>
  );
}
