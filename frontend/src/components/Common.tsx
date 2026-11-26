import { useLayoutEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useApp } from '../AppContext';
import type { PlayerDirectoryRow } from '../types';
import { teamLogo } from '../utils';
import { Avatar } from './Avatar';
import { CompareIcon, HeartIcon } from './Icons';

export function PageHead({ title, intro, children }: { title: string; intro: string; children?: ReactNode }) {
  return <div className="page-head"><div><h1>{title}</h1><p>{intro}</p></div>{children}</div>;
}

export function PlayerCell({ player, note }: { player: PlayerDirectoryRow; note?: string }) {
  const { open } = useApp();
  return (
    <button type="button" className="player-link player-cell" onClick={() => open(player.player_id)}>
      <Avatar key={player.nba_player_id} name={player.full_name} nbaPlayerId={player.nba_player_id} className="player-thumb" />
      <span className="player-cell-text"><span className="player-name">{player.full_name}</span><small>{note ?? [player.club, player.position].filter(Boolean).join(', ')}</small></span>
    </button>
  );
}

export function RowActions({ player }: { player: PlayerDirectoryRow }) {
  const { favoriteIds, compareWith, toggleFavorite, user } = useApp();
  const favorite = favoriteIds.includes(player.player_id);
  return (
    <div className="row-actions">
      <button type="button" className="icon-button compare-toggle" title="Compare with…" aria-label={`Compare ${player.full_name} with other players`} onClick={() => compareWith(player.player_id)}><CompareIcon /></button>
      {user && <button type="button" className={`icon-button favorite-button ${favorite ? 'is-favorite' : ''}`} aria-pressed={favorite} title={favorite ? 'Remove from shortlist' : 'Shortlist'} aria-label={`Shortlist ${player.full_name}`} onClick={() => toggleFavorite(player.player_id)}><HeartIcon filled={favorite} /></button>}
    </div>
  );
}

/** Tabs with an orange thumb that slides to the chosen one. */
export function Segmented<T extends string>({ label, value, options, onChange }: { label: string; value: T; options: [T, string][]; onChange: (v: T) => void }) {
  const box = useRef<HTMLDivElement>(null);
  const [thumb, setThumb] = useState<{ left: number; width: number } | null>(null);
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    const place = () => {
      const active = el.querySelector<HTMLButtonElement>('.segment.active');
      setThumb(active ? { left: active.offsetLeft, width: active.offsetWidth } : null);
    };
    place();
    const watch = new ResizeObserver(place);
    watch.observe(el);
    return () => watch.disconnect();
  }, [value, options.length]);
  return (
    <div className="segmented has-thumb" role="group" aria-label={label} ref={box}>
      {thumb && <span className="segmented-thumb" aria-hidden="true" style={{ transform: `translateX(${thumb.left}px)`, width: thumb.width }} />}
      {options.map(([key, text]) => <button key={key} type="button" aria-pressed={value === key} className={value === key ? 'segment active' : 'segment'} onClick={() => onChange(key)}>{text}</button>)}
    </div>
  );
}

export function TeamLogo({ teamId, size = 24 }: { teamId: number | null; size?: number }) {
  const src = teamLogo(teamId);
  return src ? <img className="team-logo" src={src} alt="" width={size} height={size} loading="lazy" onError={(e) => { e.currentTarget.style.visibility = 'hidden'; }} /> : null;
}

export function Loading({ height = '20rem' }: { height?: string }) {
  return <span className="skeleton" role="status" aria-label="Loading" style={{ height, marginTop: '1.1rem', borderRadius: 16 }} />;
}

export function LoadError({ message }: { message: string }) {
  return <div className="panel"><p className="status error" role="alert">{message} Check that the backend is running, then reload the page.</p></div>;
}
