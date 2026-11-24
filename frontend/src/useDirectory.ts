import { useEffect, useMemo, useState } from 'react';
import { EMPTY_STAT_FILTERS } from './types';
import type { DirectoryStatFilters, PlayerDirectoryRow, PlayerTotals, SortDirection, SortKey } from './types';
import { plain } from './utils';

export const PAGE_SIZE = 25;

/** Text columns sort A-Z first; numeric columns start with the biggest value. */
const defaultDirection = (key: SortKey): SortDirection => (key === 'name' || key === 'club' ? 'asc' : 'desc');

export function useDirectory() {
  const [players, setPlayers] = useState<PlayerDirectoryRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [club, setClub] = useState('');
  const [statFilters, setStatFilters] = useState<DirectoryStatFilters>(EMPTY_STAT_FILTERS);
  const [sortKey, setSortKey] = useState<SortKey>('points');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [page, setPage] = useState(1);
  const [compact, setCompact] = useState(false);
  const [mode, setMode] = useState<'pergame' | 'totals'>('pergame');
  const [totals, setTotals] = useState<Record<number, PlayerTotals>>({});

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const response = await fetch('/api/players/directory');
        if (!response.ok) throw new Error('Unable to load players from API.');
        const rows = (await response.json()) as PlayerDirectoryRow[];
        if (!cancelled) setPlayers(rows);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Unknown error while loading players.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    (async () => {
      try {
        const response = await fetch('/api/players/totals');
        if (!response.ok) return;
        const rows = (await response.json()) as PlayerTotals[];
        if (!cancelled) setTotals(Object.fromEntries(rows.map((row) => [row.player_id, row])));
      } catch { /* totals are optional; cells show a dash */ }
    })();
    return () => { cancelled = true; };
  }, []);

  const filtered = useMemo(() => {
    const term = plain(query.trim());
    const matches = players.filter((player) => {
      if (term && !plain(player.full_name).includes(term)) return false;
      if (club && player.club_full_name !== club) return false;
      return (Object.entries(statFilters) as [keyof DirectoryStatFilters, number][]).every(([key, bound]) => {
        if (!bound) return true;
        const value = (player[key] as number | null) ?? 0;
        return key === 'turnovers' ? value <= bound : value >= bound;
      });
    });
    const valueOf = (player: PlayerDirectoryRow): string | number | null => {
      if (sortKey === 'name') return player.full_name;
      if (sortKey === 'club') return player.club_full_name ?? '';
      const t = totals[player.player_id];
      if (sortKey === 'plus_minus') return t ? (mode === 'totals' ? t.plus_minus : t.plus_minus / t.games_played) : null;
      if (mode === 'pergame') return player[sortKey];
      if (!t) return null;
      if (sortKey === 'field_goal_pct') return t.field_goals_made;
      if (sortKey === 'three_point_pct') return t.three_pointers_made;
      if (sortKey === 'free_throw_pct') return t.free_throws_made;
      return t[sortKey];
    };
    const sign = sortDirection === 'asc' ? 1 : -1;
    return matches.map((player) => ({ player, value: valueOf(player) })).sort((a, b) => {
      if (a.value == null || b.value == null) return (a.value == null ? 1 : 0) - (b.value == null ? 1 : 0); // missing values last, both ways
      return sign * (typeof a.value === 'string' ? a.value.localeCompare(b.value as string) : a.value - (b.value as number));
    }).map((entry) => entry.player);
  }, [players, totals, mode, query, club, statFilters, sortKey, sortDirection]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const paged = useMemo(() => filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE), [filtered, safePage]);
  const clubOptions = useMemo(() => [...new Set(players.map((p) => p.club_full_name).filter((c): c is string => Boolean(c)))].sort(), [players]);
  const activeFilterCount = (query.trim() ? 1 : 0) + (club ? 1 : 0) + Object.values(statFilters).filter((v) => v > 0).length;

  useEffect(() => { setPage(1); }, [mode, query, club, statFilters, sortKey, sortDirection]);

  const sortBy = (key: SortKey) => {
    if (sortKey === key) setSortDirection((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortKey(key); setSortDirection(defaultDirection(key)); }
  };
  const clearFilters = () => { setQuery(''); setClub(''); setStatFilters(EMPTY_STAT_FILTERS); };

  return { players, loading, error, query, setQuery, club, setClub, statFilters, setStatFilters, sortKey, sortDirection, sortBy, page: safePage, setPage, pageCount, filtered, paged, clubOptions, activeFilterCount, clearFilters, compact, setCompact, mode, setMode, totals };
}

export type DirectoryState = ReturnType<typeof useDirectory>;
