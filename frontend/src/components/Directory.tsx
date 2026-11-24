import { useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import { PAGE_SIZE } from '../useDirectory';
import type { DirectoryState } from '../useDirectory';
import { EMPTY_STAT_FILTERS } from '../types';
import type { DirectoryStatFilters, PlayerDirectoryRow, SortKey } from '../types';
import { scaledPct, teamLogo } from '../utils';
import { CompareIcon, HeartIcon, SearchIcon, SlidersIcon } from './Icons';
import { PlayerLink } from './PlayerLink';

/** Same columns in both modes, so switching never moves anything. */
const COLUMNS: [SortKey, string, string][] = [['games_played', 'GP', 'GP'], ['minutes', 'MIN', 'MIN'], ['points', 'PTS', 'PTS'], ['rebounds', 'REB', 'REB'], ['assists', 'AST', 'AST'], ['steals', 'STL', 'STL'], ['blocks', 'BLK', 'BLK'], ['turnovers', 'TOV', 'TOV'], ['field_goal_pct', 'FG%', 'FG'], ['three_point_pct', '3P%', '3P'], ['free_throw_pct', 'FT%', 'FT'], ['plus_minus', '+/−', '+/−']];
const FILTERS: [keyof DirectoryStatFilters, string, string, number, number][] = [
  ['points', 'Points', 'PTS', 40, 0.5], ['rebounds', 'Rebounds', 'REB', 20, 0.5], ['assists', 'Assists', 'AST', 15, 0.5], ['minutes', 'Minutes', 'MIN', 40, 0.5], ['steals', 'Steals', 'STL', 5, 0.1],
  ['blocks', 'Blocks', 'BLK', 5, 0.1], ['turnovers', 'Turnovers', 'TOV', 10, 0.1], ['field_goal_pct', 'Field goal', 'FG%', 100, 1], ['three_point_pct', 'Three-point', '3P%', 100, 1], ['free_throw_pct', 'Free throw', 'FT%', 100, 1],
];
const PRESETS: [string, Partial<DirectoryStatFilters>][] = [
  ['Scorers', { points: 20 }], ['Playmakers', { assists: 6 }], ['Rebounders', { rebounds: 8 }], ['Shooters', { three_point_pct: 38, minutes: 20 }], ['Defenders', { steals: 1.2, blocks: 1 }], ['Workhorses', { minutes: 32 }],
];
const MAX_COMPARE = 3;

type Props = {
  dir: DirectoryState;
  favoriteIds: number[];
  compareIds: number[];
  onToggleFavorite: (playerId: number) => void;
  onToggleCompare: (playerId: number) => void;
  onOpen: (playerId: number) => void;
};

function Segmented<T extends string>({ label, value, options, onChange }: { label: string; value: T; options: [T, string][]; onChange: (v: T) => void }) {
  return (
    <div className="segmented-group">
      <span className="segmented-label">{label}</span>
      <div className="segmented" role="group" aria-label={label}>
        {options.map(([key, text]) => <button key={key} type="button" aria-pressed={value === key} className={value === key ? 'segment active' : 'segment'} onClick={() => onChange(key)}>{text}</button>)}
      </div>
    </div>
  );
}

function SortHeader({ dir, column, label, left }: { dir: DirectoryState; column: SortKey; label: string; left?: boolean }) {
  const active = dir.sortKey === column;
  return (
    <th scope="col" aria-sort={active ? (dir.sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'} className={`${active ? 'sorted' : ''} ${left ? 'left' : ''}`}>
      <button type="button" className="sort-heading" onClick={() => dir.sortBy(column)}>
        {label}<span className="sort-arrow" aria-hidden="true">{active ? (dir.sortDirection === 'asc' ? '▲' : '▼') : '▼'}</span>
      </button>
    </th>
  );
}

function FilterPanel({ dir }: { dir: DirectoryState }) {
  const activeCount = Object.values(dir.statFilters).filter((v) => v > 0).length;
  return (
    <div className="filter-panel">
      <div className="filter-panel-head">
        <div className="preset-row"><span>Quick picks</span>{PRESETS.map(([name, values]) => <button key={name} type="button" className="chip" onClick={() => dir.setStatFilters({ ...EMPTY_STAT_FILTERS, ...values })}>{name}</button>)}</div>
        <button type="button" className="link-button" disabled={!activeCount} onClick={() => dir.setStatFilters(EMPTY_STAT_FILTERS)}>Reset</button>
      </div>
      <div className="filter-cards">
        {FILTERS.map(([key, label, short, max, step]) => {
          const value = dir.statFilters[key];
          const pct = key.includes('pct');
          return (
            <label key={key} className={`filter-card ${value > 0 ? 'set' : ''}`} style={{ '--fill': `${(value / max) * 100}%` } as CSSProperties}>
              <span className="filter-card-top"><small>{label}</small><abbr title={label}>{short}</abbr></span>
              <output>{value > 0 ? <><em>{key === 'turnovers' ? '≤' : '≥'}</em> {value.toFixed(step < 1 ? 1 : 0)}{pct ? '%' : ''}</> : 'Any'}</output>
              <input type="range" min={0} max={max} step={step} value={value} aria-label={`${key === 'turnovers' ? 'Maximum' : 'Minimum'} ${label.toLowerCase()}`} onChange={(e) => dir.setStatFilters((f) => ({ ...f, [key]: Number(e.target.value) }))} />
            </label>
          );
        })}
      </div>
    </div>
  );
}

export function Directory({ dir, favoriteIds, compareIds, onToggleFavorite, onToggleCompare, onOpen }: Props) {
  const [showFilters, setShowFilters] = useState(false);
  const totalsMode = dir.mode === 'totals';
  const compareFull = compareIds.length >= MAX_COMPARE;
  const filterCount = Object.values(dir.statFilters).filter((v) => v > 0).length;
  const tableRef = useRef<HTMLDivElement>(null);
  const turnPage = (page: number) => { dir.setPage(page); tableRef.current?.scrollIntoView({ block: 'start' }); };
  const columnCount = COLUMNS.length + 3;
  const signed = (v: number, digits: number) => `${v > 0 ? '+' : ''}${v.toFixed(digits)}`;

  const renderRow = (player: PlayerDirectoryRow, index: number) => {
    const favorite = favoriteIds.includes(player.player_id);
    const comparing = compareIds.includes(player.player_id);
    const t = dir.totals[player.player_id];
    const one = (v: number | null) => v?.toFixed(1) ?? '–';
    const cells: (string | number)[] = totalsMode
      ? (t ? [t.games_played, t.minutes.toLocaleString(), t.points.toLocaleString(), t.rebounds, t.assists, t.steals, t.blocks, t.turnovers, `${t.field_goals_made}/${t.field_goals_attempted}`, `${t.three_pointers_made}/${t.three_pointers_attempted}`, `${t.free_throws_made}/${t.free_throws_attempted}`, signed(t.plus_minus, 0)] : COLUMNS.map(() => '–'))
      : [player.games_played ?? '–', one(player.minutes), one(player.points), one(player.rebounds), one(player.assists), one(player.steals), one(player.blocks), one(player.turnovers), scaledPct(player.field_goal_pct), scaledPct(player.three_point_pct), scaledPct(player.free_throw_pct), t ? signed(t.plus_minus / t.games_played, 1) : '–'];
    return (
      <tr key={player.player_id} style={{ animationDelay: `${Math.min(index, 12) * 20}ms` }}>
        <td className="sticky-col"><div className="cell-clip"><PlayerLink playerId={player.player_id} name={player.full_name} nbaPlayerId={player.nba_player_id} onOpen={onOpen} />{!player.is_active && <span className="inactive-tag">Inactive</span>}</div></td>
        <td className="left"><span className="club-cell" title={player.club_full_name ?? ''}>{teamLogo(player.club_team_id) && <img src={teamLogo(player.club_team_id) ?? ''} alt="" loading="lazy" onError={(e) => { e.currentTarget.style.display = 'none'; }} />}{player.club ?? '–'}</span></td>
        {cells.map((value, i) => <td key={COLUMNS[i][0]} className={`${dir.sortKey === COLUMNS[i][0] ? 'sorted-cell' : ''} ${totalsMode && COLUMNS[i][0].endsWith('_pct') ? 'fraction' : ''}`}>{value}</td>)}
        <td>
          <div className="row-actions">
            <button type="button" className={`icon-button compare-toggle ${comparing ? 'on' : ''}`} aria-pressed={comparing} disabled={!comparing && compareFull} title={comparing ? 'Remove from comparison' : compareFull ? `Compare is limited to ${MAX_COMPARE} players` : 'Add to comparison'} aria-label={`${comparing ? 'Remove' : 'Add'} ${player.full_name} ${comparing ? 'from' : 'to'} comparison`} onClick={() => onToggleCompare(player.player_id)}><CompareIcon /></button>
            <button type="button" className={`icon-button favorite-button ${favorite ? 'is-favorite' : ''}`} aria-pressed={favorite} onClick={() => onToggleFavorite(player.player_id)} aria-label={`${favorite ? 'Remove' : 'Add'} ${player.full_name} ${favorite ? 'from' : 'to'} shortlist`}><HeartIcon filled={favorite} /></button>
          </div>
        </td>
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
        <select value={dir.club} onChange={(e) => dir.setClub(e.target.value)} aria-label="Filter by club" className="control-input">
          <option value="">All clubs</option>
          {dir.clubOptions.map((club) => <option key={club} value={club}>{club}</option>)}
        </select>
        <button type="button" className={`filter-button ${showFilters ? 'open' : ''}`} aria-expanded={showFilters} onClick={() => setShowFilters((v) => !v)}>
          <SlidersIcon /> Stat filters{filterCount > 0 && <b>{filterCount}</b>}
        </button>
      </div>

      {showFilters && <FilterPanel dir={dir} />}

      {dir.activeFilterCount > 0 && (
        <div className="active-filters">
          <span>{dir.activeFilterCount} active {dir.activeFilterCount === 1 ? 'filter' : 'filters'}</span>
          <button type="button" className="link-button" onClick={dir.clearFilters}>Clear all filters</button>
        </div>
      )}

      {dir.error && <p className="status error" role="alert">{dir.error}</p>}

      {!dir.error && (
        <>
          <div className="table-controls">
            <Segmented label="Stats" value={dir.mode} options={[['pergame', 'Per game'], ['totals', 'Season totals']]} onChange={dir.setMode} />
            <Segmented label="Rows" value={dir.compact ? 'compact' : 'comfortable'} options={[['comfortable', 'Comfortable'], ['compact', 'Compact']]} onChange={(v) => dir.setCompact(v === 'compact')} />
          </div>
          <div ref={tableRef} className={`table-wrap ${dir.compact ? 'compact' : ''}`} tabIndex={0} aria-label="Player statistics table">
            <table className="directory-table">
              <colgroup>
                <col className="col-name" /><col className="col-club" />
                {COLUMNS.map(([key]) => <col key={key} className={key.endsWith('_pct') ? 'col-shooting' : 'col-stat'} />)}
                <col className="col-actions" />
              </colgroup>
              <thead>
                <tr>
                  <SortHeader dir={dir} column="name" label="Name" left />
                  <SortHeader dir={dir} column="club" label="Team" left />
                  {COLUMNS.map(([key, perGame, total]) => <SortHeader key={key} dir={dir} column={key} label={totalsMode ? total : perGame} />)}
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
          <div className="pagination">
            <button type="button" className="nav-button" disabled={dir.page <= 1} onClick={() => turnPage(dir.page - 1)}>Prev</button>
            <span>{dir.filtered.length ? `${(dir.page - 1) * PAGE_SIZE + 1}–${Math.min(dir.page * PAGE_SIZE, dir.filtered.length)} of ${dir.filtered.length}` : '0 players'}</span>
            <button type="button" className="nav-button" disabled={dir.page >= dir.pageCount} onClick={() => turnPage(dir.page + 1)}>Next</button>
          </div>
        </>
      )}
    </section>
  );
}
