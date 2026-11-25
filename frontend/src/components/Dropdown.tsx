import { useEffect, useId, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent, ReactNode } from 'react';
import { useApp } from '../AppContext';
import { STATS } from '../stats';
import { plain } from '../utils';
import { TeamLogo } from './Common';
import { SearchIcon } from './Icons';

export type Option = { value: string; label: string; icon?: ReactNode; note?: string; group?: string };
type Props = { label: string; value: string; options: Option[]; onChange: (value: string) => void; search?: string; wide?: boolean; className?: string; showLabel?: boolean };

/** A listbox that can show logos: arrow keys, Enter, Escape and typing to search all work. */
export function Dropdown({ label, value, options, onChange, search, wide, className = '', showLabel }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const id = useId();
  const current = options.find((o) => o.value === value);
  const shown = useMemo(() => { const term = plain(query.trim()); return term ? options.filter((o) => plain(`${o.label} ${o.note ?? ''}`).includes(term)) : options; }, [options, query]);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (!root.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [open]);
  useEffect(() => { if (open) list.current?.querySelector('.active')?.scrollIntoView({ block: 'nearest' }); }, [open, active]);

  const show = () => { setQuery(''); setActive(Math.max(0, options.findIndex((o) => o.value === value))); setOpen(true); };
  const hide = () => { setOpen(false); root.current?.querySelector('button')?.focus(); };
  const pick = (option?: Option) => { if (option) { onChange(option.value); hide(); } };
  const onKey = (e: KeyboardEvent) => {
    if (!open) { if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); show(); } return; }
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); if (shown.length) setActive((i) => (i + (e.key === 'ArrowDown' ? 1 : -1) + shown.length) % shown.length); }
    else if (e.key === 'Enter') { e.preventDefault(); pick(shown[active]); }
    else if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); hide(); }
    else if (e.key === 'Tab') setOpen(false);
  };
  return (
    <div className={`dd ${open ? 'open' : ''} ${className}`} ref={root} onKeyDown={onKey}>
      {showLabel && <span className="dd-label" id={`${id}-label`}>{label}</span>}
      <button type="button" className={`dd-button ${value ? 'set' : ''}`} aria-haspopup="listbox" aria-expanded={open} aria-label={`${label}: ${current?.label ?? ''}`} onClick={() => (open ? setOpen(false) : show())}>
        {current?.icon}<span>{current?.label ?? label}</span><i className="caret" aria-hidden="true" />
      </button>
      {open && (
        <div className={`dd-pop ${wide ? 'wide' : ''}`}>
          {search && <div className="search-field"><SearchIcon /><input autoFocus className="control-input" aria-label={search} placeholder={search} value={query} onChange={(e) => { setQuery(e.target.value); setActive(0); }} /></div>}
          <ul role="listbox" aria-label={label} ref={list} tabIndex={-1}>
            {shown.map((o, i) => {
              const heading = o.group && o.group !== shown[i - 1]?.group ? <li key={`g${o.group}`} role="presentation" className="dd-group">{o.group}</li> : null;
              return [heading, (
                <li key={o.value} role="option" aria-selected={o.value === value} className={`${i === active ? 'active' : ''} ${o.value === value ? 'chosen' : ''}`} onMouseEnter={() => setActive(i)} onClick={() => pick(o)}>
                  {o.icon}<span>{o.label}</span>{o.note && <small>{o.note}</small>}
                </li>
              )];
            })}
            {!shown.length && <li className="none">Nothing found</li>}
          </ul>
        </div>
      )}
    </div>
  );
}

const EAST = new Set(['ATL', 'BOS', 'BKN', 'CHA', 'CHI', 'CLE', 'DET', 'IND', 'MIA', 'MIL', 'NYK', 'ORL', 'PHI', 'TOR', 'WAS']);
export type TeamRef = { id: number; name: string; abbr: string };
/** Every team that appears in the directory, in alphabetical order. */
export function useTeamList(): TeamRef[] {
  const { players } = useApp();
  return useMemo(() => {
    const map = new Map<number, TeamRef>();
    for (const p of players) if (p.club_team_id != null && !map.has(p.club_team_id)) map.set(p.club_team_id, { id: p.club_team_id, name: p.club_full_name ?? '', abbr: p.club ?? '' });
    return [...map.values()].sort((a, b) => a.name.localeCompare(b.name));
  }, [players]);
}

/** value is the team's full name, '' for all. */
export function TeamSelect({ value, onChange, label = 'Team', all = 'All teams', by = 'name' }: { value: string; onChange: (v: string) => void; label?: string; all?: string; by?: 'name' | 'abbr' | 'id' }) {
  const teams = useTeamList();
  const options = useMemo<Option[]>(() => [
    { value: '', label: all, icon: <span className="dd-ball" aria-hidden="true" /> },
    ...['East', 'West'].flatMap((side) => teams.filter((t) => EAST.has(t.abbr) === (side === 'East')).map((t) => ({ value: String(t[by]), label: t.name, note: t.abbr, group: `${side}ern Conference`, icon: <TeamLogo teamId={t.id} size={26} /> }))),
  ], [teams, all, by]);
  return <Dropdown label={label} value={value} options={options} onChange={onChange} search="Search teams" wide className="team-select" />;
}

/** `keys` narrows the list; by default every statistic is offered, grouped. */
export function StatSelect({ value, onChange, label, showLabel, keys }: { value: string; onChange: (v: string) => void; label: string; showLabel?: boolean; keys?: string[] }) {
  const options = useMemo<Option[]>(() => STATS.filter((s) => !keys || keys.includes(s.key)).map((s) => ({ value: s.key, label: s.label, note: s.short, group: s.group })), [keys]);
  return <Dropdown label={label} value={value} options={options} onChange={onChange} search="Search statistics" showLabel={showLabel} />;
}
