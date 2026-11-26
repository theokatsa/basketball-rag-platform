import { useEffect, useMemo, useState } from 'react';
import { statByKey } from './stats';
import type { FilterRule, PlayerDirectoryRow, PlayerTotals, SortDirection, SortKey } from './types';
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
  const [position, setPosition] = useState('');
  const [rules, setRules] = useState<FilterRule[]>([]);
  const [sortKey, setSortKey] = useState<SortKey>('points');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [page, setPage] = useState(1);
  const [detailed, setDetailed] = useState(false);
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
      if (position && !(player.position ?? '').includes(position)) return false;
      return rules.every(({ stat, op, value }) => {
        const own = statByKey(stat).get(player, totals[player.player_id]);
        return own != null && (op === 'min' ? own >= value : own <= value);
      });
    });
    const valueOf = (player: PlayerDirectoryRow): string | number | null => {
      if (sortKey === 'name') return player.full_name;
      if (sortKey === 'club') return player.club_full_name ?? '';
      const stat = statByKey(sortKey), t = totals[player.player_id];
      if (mode === 'pergame' || !stat.total) return stat.get(player, t);
      return t ? parseFloat(String(stat.total(t))) : null;
    };
    const sign = sortDirection === 'asc' ? 1 : -1;
    return matches.map((player) => ({ player, value: valueOf(player) })).sort((a, b) => {
      if (a.value == null || b.value == null) return (a.value == null ? 1 : 0) - (b.value == null ? 1 : 0); // missing values last, both ways
      return sign * (typeof a.value === 'string' ? a.value.localeCompare(b.value as string) : a.value - (b.value as number));
    }).map((entry) => entry.player);
  }, [players, totals, mode, query, club, position, rules, sortKey, sortDirection]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const paged = useMemo(() => filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE), [filtered, safePage]);
  const filterCount = (query.trim() ? 1 : 0) + (club ? 1 : 0) + (position ? 1 : 0) + rules.length;

  useEffect(() => { setPage(1); }, [mode, query, club, position, rules, sortKey, sortDirection]);

  const sortBy = (key: SortKey) => {
    if (sortKey === key) setSortDirection((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortKey(key); setSortDirection(defaultDirection(key)); }
  };
  const clearFilters = () => { setQuery(''); setClub(''); setPosition(''); setRules([]); };
  /** The directory as it first opens: no filters, sorted by points, first page. */
  const reset = () => { clearFilters(); setSortKey('points'); setSortDirection('desc'); setDetailed(false); setMode('pergame'); setPage(1); };

  return { players, loading, error, query, setQuery, club, setClub, position, setPosition, rules, setRules, sortKey, sortDirection, sortBy, page: safePage, setPage, pageCount, filtered, paged, filterCount, clearFilters, reset, detailed, setDetailed, mode, setMode, totals };
}

export type DirectoryState = ReturnType<typeof useDirectory>;
