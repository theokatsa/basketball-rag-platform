import { createContext, useContext } from 'react';
import type { PlayerDirectoryRow, PlayerTotals, View } from './types';

export type AppData = {
  players: PlayerDirectoryRow[];
  totals: Record<number, PlayerTotals>;
  byId: Map<number, PlayerDirectoryRow>;
  loading: boolean;
  error: string | null;
  favoriteIds: number[];
  compareIds: number[];
  historyIds: number[];
  toggleFavorite: (playerId: number) => void;
  toggleCompare: (playerId: number) => void;
  open: (playerId: number) => void;
  go: (view: View, id?: number) => void;
};

export const AppContext = createContext<AppData | null>(null);

export function useApp(): AppData {
  const value = useContext(AppContext);
  if (!value) throw new Error('useApp must be used inside AppContext');
  return value;
}
