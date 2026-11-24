import { useState } from 'react';
import type { FormEvent } from 'react';
import type { PlayerDirectoryRow } from '../types';
import { CompareIcon, HeartIcon } from './Icons';
import { PlayerLink } from './PlayerLink';

type Props = {
  favoritePlayers: PlayerDirectoryRow[];
  groups: Record<string, number[]>;
  setGroups: (updater: (current: Record<string, number[]>) => Record<string, number[]>) => void;
  compareIds: number[];
  onToggleFavorite: (playerId: number) => void;
  onToggleCompare: (playerId: number) => void;
  onOpen: (playerId: number) => void;
};

const ALL = 'All saved';

export function Shortlist({ favoritePlayers, groups, setGroups, compareIds, onToggleFavorite, onToggleCompare, onOpen }: Props) {
  const [newGroupName, setNewGroupName] = useState('');
  const [activeGroup, setActiveGroup] = useState(ALL);
  const groupNames = Object.keys(groups);
  const visible = activeGroup === ALL ? favoritePlayers : favoritePlayers.filter((p) => groups[activeGroup]?.includes(p.player_id));

  const createGroup = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const name = newGroupName.trim();
    if (!name || name === ALL || groups[name]) return;
    setGroups((current) => ({ ...current, [name]: [] }));
    setNewGroupName('');
    setActiveGroup(name);
  };

  /** A player belongs to at most one group; choosing "No group" removes them. */
  const assign = (playerId: number, groupName: string) => setGroups((current) => {
    const next: Record<string, number[]> = {};
    for (const [name, ids] of Object.entries(current)) next[name] = ids.filter((id) => id !== playerId);
    if (groupName) next[groupName] = [...(next[groupName] ?? []), playerId];
    return next;
  });

  const deleteGroup = (name: string) => {
    setGroups((current) => Object.fromEntries(Object.entries(current).filter(([key]) => key !== name)));
    setActiveGroup(ALL);
  };

  return (
    <section className="panel shortlist-page">
      <div className="panel-header"><div><h2>Your Shortlist</h2></div><p className="count-label">{visible.length} saved players</p></div>
      <div className="group-toolbar">
        <div className="group-tabs" role="tablist" aria-label="Scouting groups">
          {[ALL, ...groupNames].map((name) => <button type="button" role="tab" aria-selected={activeGroup === name} className={activeGroup === name ? 'group-tab active' : 'group-tab'} key={name} onClick={() => setActiveGroup(name)}>{name}{name !== ALL && <span className="tab-count">{groups[name]?.length ?? 0}</span>}</button>)}
        </div>
        <form className="group-create" onSubmit={createGroup}>
          <input className="control-input" aria-label="New group name" value={newGroupName} onChange={(e) => setNewGroupName(e.target.value)} placeholder="New scouting group (e.g. Sixth Man)" />
          <button className="nav-button" type="submit" disabled={!newGroupName.trim()}>Create group</button>
          {activeGroup !== ALL && <button className="ghost-button" type="button" onClick={() => deleteGroup(activeGroup)}>Delete “{activeGroup}”</button>}
        </form>
      </div>
      {visible.length ? (
        <div className="shortlist-table">
          <div className="group-assignment-label">Assign saved players to a scouting role</div>
          {visible.map((player) => {
            const comparing = compareIds.includes(player.player_id);
            return (
              <div className="shortlist-row" key={player.player_id}>
                <PlayerLink playerId={player.player_id} name={player.full_name} nbaPlayerId={player.nba_player_id} onOpen={onOpen} />
                <span className="club-cell">{player.club_full_name ?? player.club ?? '-'}</span>
                <span className="line-stats"><b>{player.points?.toFixed(1) ?? '–'}</b> pts <b>{player.rebounds?.toFixed(1) ?? '–'}</b> reb <b>{player.assists?.toFixed(1) ?? '–'}</b> ast</span>
                <select className="control-input group-select" aria-label={`Group for ${player.full_name}`} value={groupNames.find((n) => groups[n]?.includes(player.player_id)) ?? ''} onChange={(e) => assign(player.player_id, e.target.value)}>
                  <option value="">No group</option>
                  {groupNames.map((name) => <option value={name} key={name}>{name}</option>)}
                </select>
                <div className="row-actions">
                  <button type="button" className={`icon-button compare-toggle ${comparing ? 'on' : ''}`} aria-pressed={comparing} disabled={!comparing && compareIds.length >= 3} aria-label={`${comparing ? 'Remove' : 'Add'} ${player.full_name} ${comparing ? 'from' : 'to'} comparison`} onClick={() => onToggleCompare(player.player_id)}><CompareIcon /></button>
                  <button type="button" className="icon-button favorite-button is-favorite" onClick={() => onToggleFavorite(player.player_id)} aria-label={`Remove ${player.full_name} from shortlist`}><HeartIcon filled /></button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="empty-state"><span className="empty-mark"><HeartIcon /></span><p>{activeGroup === ALL ? 'Your shortlist is empty.' : 'This group has no players yet.'}</p><small>Save players and organize them into roles such as Sixth Man or Starting PG replacement.</small></div>
      )}
    </section>
  );
}
