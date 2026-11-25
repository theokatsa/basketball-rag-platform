import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { formatStat, POSITIONS, statByKey } from '../stats';
import type { DirectoryState } from '../useDirectory';
import { teamVars } from '../teamColors';
import type { PlayerDirectoryRow, SortKey } from '../types';
import { RowActions, Segmented, TeamLogo } from './Common';
import { Dropdown, StatSelect, TeamSelect } from './Dropdown';
import { CloseIcon, SearchIcon } from './Icons';
import { Pagination } from './Pagination';
import { PlayerLink } from './PlayerLink';

const MAIN = ['games_played', 'minutes', 'points', 'rebounds', 'assists', 'fg', 'three', 'ft'];
const DETAILED = ['games_played', 'minutes', 'points', 'rebounds', 'oreb', 'dreb', 'assists', 'turnovers', 'steals', 'blocks', 'pf', 'fg', 'three', 'ft', 'threes', 'ts', 'efg', 'usage', 'ast_pct', 'dfg_diff', 'off_rating', 'def_rating', 'net_rating', 'plus_minus', 'production', 'double_doubles', 'age'];

function SortHeader({ dir, column, label, title, left }: { dir: DirectoryState; column: SortKey; label: string; title?: string; left?: boolean }) {
  const active = dir.sortKey === column;
  return (
    <th scope="col" title={title} aria-sort={active ? (dir.sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'} className={`${active ? 'sorted' : ''} ${left ? 'left' : ''}`}>
      <button type="button" className="sort-heading" onClick={() => dir.sortBy(column)}>
        {label}<span className="sort-arrow" aria-hidden="true">{active ? (dir.sortDirection === 'asc' ? '▲' : '▼') : '▼'}</span>
      </button>
    </th>
  );
}

/** "Points at least 20" – add as many lines as needed. */
function FilterBuilder({ dir }: { dir: DirectoryState }) {
  const [stat, setStat] = useState('points');
  const [op, setOp] = useState<'min' | 'max'>('min');
  const [value, setValue] = useState('');
  const def = statByKey(stat);
  const number = Number(value.replace(',', '.'));
  const valid = value.trim() !== '' && Number.isFinite(number);
  const add = (e: FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    dir.setRules((rules) => [...rules.filter((r) => r.stat !== stat || r.op !== op), { id: Date.now(), stat, op, value: number }]);
    setValue('');
  };
  return (
    <form className="rule-builder" onSubmit={add}>
      <span className="rule-lead">Only players with</span>
      <StatSelect label="Statistic" value={stat} onChange={setStat} />
      <Dropdown label="Condition" value={op} options={[{ value: 'min', label: 'at least' }, { value: 'max', label: 'at most' }]} onChange={(v) => setOp(v as 'min' | 'max')} />
      <span className="rule-value"><input className="control-input" inputMode="decimal" aria-label={`Value for ${def.label}`} placeholder="Value" value={value} onChange={(e) => setValue(e.target.value)} />{def.suffix && <i>{def.suffix}</i>}</span>
      <button type="submit" className="ghost-button" disabled={!valid}>Add filter</button>
    </form>
  );
}

export function Directory({ dir, onOpen }: { dir: DirectoryState; onOpen: (playerId: number) => void }) {
  const totalsMode = dir.mode === 'totals';
  const columns = (dir.detailed ? DETAILED : MAIN).map(statByKey);
  const tableRef = useRef<HTMLDivElement>(null);
  const turnPage = (page: number) => { dir.setPage(page); tableRef.current?.scrollIntoView({ block: 'start' }); };
  const columnCount = columns.length + 3;

  const renderRow = (player: PlayerDirectoryRow) => {
    const t = dir.totals[player.player_id];
    return (
      <tr key={player.player_id} className="team-row" style={teamVars(player.club_team_id)}>
        <td className="sticky-col"><div className="cell-clip"><PlayerLink playerId={player.player_id} name={player.full_name} nbaPlayerId={player.nba_player_id} onOpen={onOpen} />{!player.is_active && <span className="inactive-tag">Inactive</span>}</div></td>
        <td className="left team-cell"><span className="club-cell" title={player.club_full_name ?? ''}><TeamLogo teamId={player.club_team_id} size={24} />{player.club ?? '–'}</span></td>
        {columns.map((s) => <td key={s.key} className={dir.sortKey === s.key ? 'sorted-cell' : ''}>{totalsMode && s.total ? (t ? s.total(t).toLocaleString() : '–') : formatStat(s, s.get(player, t))}</td>)}
        <td><RowActions player={player} /></td>
      </tr>
    );
  };

  return (
    <section className="panel panel-directory">
      <div className="panel-header">
        <div><h2>Player Directory</h2></div>
        <p className="count-label" aria-live="polite">{dir.filtered.length.toLocaleString()} players</p>
      </div>

      <div className="toolbar">
        <div className="search-field"><SearchIcon /><input value={dir.query} onChange={(e) => dir.setQuery(e.target.value)} placeholder="Search by player name" aria-label="Search players by name" className="control-input" /></div>
        <TeamSelect value={dir.club} onChange={dir.setClub} label="Club" all="All clubs" />
        <Segmented label="Position" value={dir.position} options={[['', 'All'], ...POSITIONS.map((p) => [p, `${p}s`] as [string, string])]} onChange={dir.setPosition} />
      </div>
      <FilterBuilder dir={dir} />
      {dir.filterCount > 0 && (
        <div className="rule-list">
          {dir.rules.map((r) => { const s = statByKey(r.stat); return <button type="button" className="rule-chip" key={r.id} aria-label={`Remove filter: ${s.label}`} onClick={() => dir.setRules((rules) => rules.filter((x) => x.id !== r.id))}>{s.label} {r.op === 'min' ? '≥' : '≤'} <b>{r.value}{s.suffix}</b><CloseIcon /></button>; })}
          <button type="button" className="link-button" onClick={dir.clearFilters}>Clear everything</button>
        </div>
      )}

      {dir.error && <p className="status error" role="alert">{dir.error}</p>}

      {!dir.error && (
        <>
          <div className="table-controls">
            <Segmented label="Columns" value={dir.detailed ? 'detailed' : 'main'} options={[['main', 'Main stats'], ['detailed', 'Detailed stats']]} onChange={(v) => dir.setDetailed(v === 'detailed')} />
            <Segmented label="Stats" value={dir.mode} options={[['pergame', 'Per game'], ['totals', 'Season totals']]} onChange={dir.setMode} />
            {dir.detailed && <span className="count-label">Hover a heading for its full name</span>}
          </div>
          <div ref={tableRef} className={`table-wrap ${dir.detailed ? 'detailed' : ''}`} tabIndex={0} aria-label="Player statistics table">
            <table className="directory-table" style={{ minWidth: dir.detailed ? 218 + 84 + columns.length * 72 + 92 : undefined }}>
              <colgroup>
                <col className="col-name" /><col className="col-club" />
                {columns.map((s) => <col key={s.key} className="col-stat" />)}
                <col className="col-actions" />
              </colgroup>
              <thead>
                <tr>
                  <SortHeader dir={dir} column="name" label="Name" left />
                  <SortHeader dir={dir} column="club" label="Team" left />
                  {columns.map((s) => <SortHeader key={s.key} dir={dir} column={s.key} title={s.label} label={totalsMode && s.total && s.suffix ? s.short.replace('%', '') : s.short} />)}
                  <th scope="col"><span className="visually-hidden">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {dir.loading
                  ? Array.from({ length: 8 }, (_, row) => <tr key={row} className="skeleton-row" aria-hidden="true">{Array.from({ length: columnCount }, (_, col) => <td key={col}><span className="skeleton" style={{ width: col === 0 ? '9rem' : '2.2rem' }} /></td>)}</tr>)
                  : dir.paged.map(renderRow)}
                {!dir.loading && !dir.paged.length && <tr><td colSpan={columnCount} className="empty-cell">No players match these filters.</td></tr>}
              </tbody>
            </table>
          </div>
          <Pagination page={dir.page} pageCount={dir.pageCount} onPage={turnPage} label="Player pages" />
        </>
      )}
    </section>
  );
}
