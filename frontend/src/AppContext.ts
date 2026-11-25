import { createContext, useContext } from 'react';
import type { PlayerDirectoryRow, PlayerTotals, User, View } from './types';

export type BrowseRequest = {
  title: string;
  /** How many players can be chosen; 1 closes the list on the first click. */
  max: number;
  min?: number;
  confirm?: string;
  selected?: number[];
  exclude?: number[];
  position?: string;
  onDone: (ids: number[]) => void;
};

export type AppData = {
  players: PlayerDirectoryRow[];
  totals: Record<number, PlayerTotals>;
  byId: Map<number, PlayerDirectoryRow>;
  loading: boolean;
  error: string | null;
  favoriteIds: number[];
  compareIds: number[];
  historyIds: number[];
  user: User | null;
  toggleFavorite: (playerId: number) => void;
  setCompareIds: (ids: number[]) => void;
  /** Opens the player list with this player already chosen. */
  compareWith: (playerId: number) => void;
  /** Opens the player list. */
  browse: (request: BrowseRequest) => void;
  open: (playerId: number) => void;
  openGame: (gameId: string) => void;
  go: (view: View, id?: number) => void;
  signedIn: (user: User, merge: boolean) => Promise<void>;
  signOut: () => Promise<void>;
};

export const AppContext = createContext<AppData | null>(null);

export function useApp(): AppData {
  const value = useContext(AppContext);
  if (!value) throw new Error('useApp must be used inside AppContext');
  return value;
}
