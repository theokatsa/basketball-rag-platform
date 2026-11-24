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
  const { favoriteIds, compareIds, toggleFavorite, toggleCompare } = useApp();
  const favorite = favoriteIds.includes(player.player_id);
  const comparing = compareIds.includes(player.player_id);
  return (
    <div className="row-actions">
      <button type="button" className={`icon-button compare-toggle ${comparing ? 'on' : ''}`} aria-pressed={comparing} disabled={!comparing && compareIds.length >= 3} title={comparing ? 'Remove from comparison' : 'Compare'} aria-label={`Compare ${player.full_name}`} onClick={() => toggleCompare(player.player_id)}><CompareIcon /></button>
      <button type="button" className={`icon-button favorite-button ${favorite ? 'is-favorite' : ''}`} aria-pressed={favorite} title={favorite ? 'Remove from shortlist' : 'Shortlist'} aria-label={`Shortlist ${player.full_name}`} onClick={() => toggleFavorite(player.player_id)}><HeartIcon filled={favorite} /></button>
    </div>
  );
}

export function Segmented<T extends string>({ label, value, options, onChange }: { label: string; value: T; options: [T, string][]; onChange: (v: T) => void }) {
  return (
    <div className="segmented" role="group" aria-label={label}>
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
