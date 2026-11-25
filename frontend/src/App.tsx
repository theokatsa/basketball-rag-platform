import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { AppContext } from './AppContext';
import type { AppData, BrowseRequest } from './AppContext';
import { Compare } from './components/Compare';
import { Directory } from './components/Directory';
import { Nav } from './components/Nav';
import { PlayerBrowser } from './components/PlayerBrowser';
import { PlayerDetail } from './components/PlayerDetail';
import { Shortlist } from './components/Shortlist';
import { Account, Login } from './pages/Account';
import { Explorer } from './pages/Explorer';
import { Game, Games } from './pages/Games';
import { Form } from './pages/Form';
import { Home } from './pages/Home';
import { Lineup } from './pages/Lineup';
import { Report } from './pages/Report';
import { Scout } from './pages/Scout';
import { ShotLab } from './pages/ShotLab';
import { Team, Teams } from './pages/Teams';
import { TopPlayers } from './pages/TopPlayers';
import { YoungTalent } from './pages/YoungTalent';
import { MAX_COMPARE } from './stats';
import type { GameLog, PlayerDetailData, PlayerProfile, PlayerRecord, ScoutNote, SeasonStat, ShotRecord, SimilarPlayerResult, User, UserState, View } from './types';
import { useDirectory } from './useDirectory';
import { forget, send } from './useApi';
import { loadStored, saveStored } from './utils';

const FAVORITES_KEY = 'basketball-scouting-favorites';
const HISTORY_KEY = 'basketball-scouting-history';
const GROUPS_KEY = 'basketball-scouting-groups';
const NOTES_KEY = 'basketball-scouting-notes';
const COMPARE_KEY = 'basketball-scouting-compare';
const HISTORY_LENGTH = 12;

type Route = { view: View; id?: number };
const PLAIN_VIEWS: View[] = ['home', 'players', 'top', 'teams', 'games', 'login', 'account', 'scout', 'explorer', 'shotlab', 'young', 'form', 'lineup', 'shortlist', 'compare'];
function parseHash(): Route {
  const [name, id] = window.location.hash.slice(1).split('/');
  if (id && /^\d+$/.test(id) && (name === 'player' || name === 'team' || name === 'report' || name === 'game')) return { view: name, id: Number(id) };
  if (name === 'directory') return { view: 'players' };
  return { view: PLAIN_VIEWS.find((v) => v === name) ?? 'home' };
}

function App() {
  const dir = useDirectory();
  const [route, setRoute] = useState<Route>(parseHash);
  const [detail, setDetail] = useState<PlayerDetailData | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const requestToken = useRef(0);

  const [favoriteIds, setFavoriteIds] = useState<number[]>(() => loadStored<number[]>(FAVORITES_KEY, []));
  const [historyIds, setHistoryIds] = useState<number[]>(() => loadStored<number[]>(HISTORY_KEY, []));
  const [groups, setGroups] = useState<Record<string, number[]>>(() => loadStored<Record<string, number[]>>(GROUPS_KEY, {}));
  const [notes, setNotes] = useState<Record<number, ScoutNote>>(() => loadStored<Record<number, ScoutNote>>(NOTES_KEY, {}));
  const [compareIds, setCompareIds] = useState<number[]>(() => loadStored<number[]>(COMPARE_KEY, []));
  useEffect(() => { saveStored(FAVORITES_KEY, favoriteIds); }, [favoriteIds]);
  useEffect(() => { saveStored(HISTORY_KEY, historyIds); }, [historyIds]);
  useEffect(() => { saveStored(GROUPS_KEY, groups); }, [groups]);
  useEffect(() => { saveStored(NOTES_KEY, notes); }, [notes]);
  useEffect(() => { saveStored(COMPARE_KEY, compareIds); }, [compareIds]);

  const [user, setUser] = useState<User | null>(null);
  const [browseRequest, setBrowseRequest] = useState<BrowseRequest | null>(null);
  const synced = useRef(false); // true once the account's saved lists are on screen

  const applyState = useCallback((state: UserState) => {
    setFavoriteIds(state.favorites ?? []);
    setGroups(state.groups ?? {});
    setHistoryIds(state.history ?? []);
    setNotes(state.notes ?? {});
  }, []);
  useEffect(() => {
    let cancelled = false;
    fetch('/api/auth/me').then((r) => (r.ok ? (r.json() as Promise<{ user: User | null; state: UserState | null }>) : null)).then((me) => {
      if (cancelled || !me?.user) return;
      setUser(me.user);
      applyState(me.state ?? {});
      synced.current = true;
    }).catch(() => { /* the API is offline; pages show their own errors */ });
    return () => { cancelled = true; };
  }, [applyState]);
  useEffect(() => {
    if (!user || !synced.current) return;
    const timer = setTimeout(() => { send('PUT', '/me/state', { favorites: favoriteIds, groups, history: historyIds, notes }).catch(() => { /* saved again on the next change */ }); }, 800);
    return () => clearTimeout(timer);
  }, [user, favoriteIds, groups, historyIds, notes]);

  /** merge: keep what was saved in this browser before signing in. */
  const signedIn = useCallback(async (next: User, merge: boolean) => {
    const { state } = await send<{ state: UserState | null }>('GET', '/auth/me');
    const saved = state ?? {};
    const both = (a: number[], b: number[] = []) => [...new Set([...a, ...b])];
    if (merge) {
      setFavoriteIds((ids) => both(ids, saved.favorites));
      setGroups((own) => Object.fromEntries([...new Set([...Object.keys(own), ...Object.keys(saved.groups ?? {})])].map((name) => [name, both(own[name] ?? [], saved.groups?.[name])])));
      setHistoryIds((ids) => both(ids, saved.history).slice(0, HISTORY_LENGTH));
      setNotes((own) => ({ ...own, ...saved.notes }));
    } else applyState(saved);
    synced.current = true;
    forget('/me/');
    setUser(next);
  }, [applyState]);
  const signOut = useCallback(async () => {
    await send('POST', '/auth/logout').catch(() => undefined);
    synced.current = false;
    setUser(null);
    applyState({});
    setCompareIds([]);
    forget('/me/');
  }, [applyState]);

  const loadPlayer = useCallback(async (playerId: number) => {
    const token = ++requestToken.current;
    setDetail(null);
    setDetailError(null);
    setDetailLoading(true);
    setHistoryIds((ids) => [playerId, ...ids.filter((id) => id !== playerId)].slice(0, HISTORY_LENGTH));
    try {
      // The heavy lists (logs, shots) load alongside but do not hold back the profile.
      const list = async <T,>(path: string): Promise<T[]> => {
        try { const r = await fetch(`/api/players/${playerId}/${path}`); return r.ok ? ((await r.json()) as T[]) : []; } catch { return []; }
      };
      const logsPromise = list<GameLog>('game-logs');
      const shotsPromise = list<ShotRecord>('shots');
      const [playerResponse, profileResponse, statsResponse, similar] = await Promise.all([
        fetch(`/api/players/${playerId}`),
        fetch(`/api/players/${playerId}/profile`),
        fetch(`/api/players/${playerId}/season-stats`),
        list<SimilarPlayerResult>('similar?limit=6'),
      ]);
      if (!playerResponse.ok || !statsResponse.ok) throw new Error('Unable to load this player profile.');
      const data: PlayerDetailData = {
        player: (await playerResponse.json()) as PlayerRecord,
        profile: profileResponse.ok ? ((await profileResponse.json()) as PlayerProfile) : { position: null, age: null, height: null, weight: null },
        stats: (await statsResponse.json()) as SeasonStat[],
        logs: null,
        shots: null,
        similar,
      };
      if (token !== requestToken.current) return;
      setDetail(data);
      const fill = (patch: Partial<PlayerDetailData>) => { if (token === requestToken.current) setDetail((current) => (current ? { ...current, ...patch } : current)); };
      void logsPromise.then((logs) => fill({ logs }));
      void shotsPromise.then((shots) => fill({ shots }));
    } catch (err) {
      if (token === requestToken.current) setDetailError(err instanceof Error ? err.message : 'Unable to load this player profile.');
    } finally {
      if (token === requestToken.current) setDetailLoading(false);
    }
  }, []);

  const playerId = route.view === 'player' ? route.id : undefined;
  useEffect(() => { if (playerId != null) void loadPlayer(playerId); }, [playerId, loadPlayer]);

  const userId = user?.id;
  useEffect(() => {
    if (playerId == null || userId == null) return;
    send('POST', `/me/views/${playerId}`).then(() => forget('/me/')).catch(() => { /* a missed view is harmless */ });
  }, [playerId, userId]);

  const go = useCallback((view: View, id?: number) => {
    setRoute({ view, id });
    window.history.pushState({ view }, '', `#${view}${id != null ? `/${id}` : ''}`);
    window.scrollTo({ top: 0 });
  }, []);
  const open = useCallback((id: number) => go('player', id), [go]);
  const goBack = () => { if ((window.history.state as { view?: View } | null)?.view) window.history.back(); else go('players'); };
  useEffect(() => {
    const onChange = () => setRoute(parseHash());
    window.addEventListener('popstate', onChange);
    return () => window.removeEventListener('popstate', onChange);
  }, []);

  const toggleFavorite = useCallback((id: number) => setFavoriteIds((ids) => (ids.includes(id) ? ids.filter((v) => v !== id) : [id, ...ids])), []);
  const setNote = useCallback((id: number, patch: Partial<ScoutNote>) => setNotes((all) => ({ ...all, [id]: { ...(all[id] ?? { text: '', stars: 0, status: '' }), ...patch } })), []);
  const openGame = useCallback((gameId: string) => go('game', Number(gameId)), [go]);
  const browse = useCallback((request: BrowseRequest) => setBrowseRequest(request), []);
  const compareWith = useCallback((id: number) => browse({ title: 'Compare with…', max: MAX_COMPARE, min: 2, confirm: 'Compare players', selected: [id], onDone: (ids) => { setCompareIds(ids); go('compare'); } }), [browse, go]);

  const byId = useMemo(() => new Map(dir.players.map((p) => [p.player_id, p])), [dir.players]);
  const app = useMemo<AppData>(() => ({ players: dir.players, totals: dir.totals, byId, loading: dir.loading, error: dir.error, favoriteIds, compareIds, historyIds, user, toggleFavorite, setCompareIds, compareWith, browse, open, openGame, go, signedIn, signOut }), [dir.players, dir.totals, dir.loading, dir.error, byId, favoriteIds, compareIds, historyIds, user, toggleFavorite, compareWith, browse, open, openGame, go, signedIn, signOut]);
  const favoritePlayers = favoriteIds.map((id) => byId.get(id)).filter((p) => p != null);

  const renderView = (): ReactNode => {
    switch (route.view) {
      case 'home': return <Home />;
      case 'players': return <Directory dir={dir} onOpen={open} />;
      case 'top': return <TopPlayers />;
      case 'teams': return <Teams />;
      case 'team': return <Team key={route.id} id={route.id ?? 0} />;
      case 'games': return <Games />;
      case 'game': return <Game key={route.id} id={String(route.id ?? 0).padStart(10, '0')} />;
      case 'login': return <Login />;
      case 'account': return <Account />;
      case 'scout': return <Scout />;
      case 'explorer': return <Explorer />;
      case 'shotlab': return <ShotLab />;
      case 'young': return <YoungTalent />;
      case 'form': return <Form />;
      case 'lineup': return <Lineup />;
      case 'report': return <Report key={route.id} id={route.id ?? 0} />;
      case 'shortlist': return <Shortlist favoritePlayers={favoritePlayers} groups={groups} setGroups={setGroups} notes={notes} setNote={setNote} onToggleFavorite={toggleFavorite} />;
      case 'compare': return <Compare onBack={goBack} />;
      case 'player': return <PlayerDetail key={route.id} detail={detail?.player.id === route.id ? detail : null} loading={detailLoading || detail?.player.id !== route.id} error={detailError} onBack={goBack} />;
    }
  };
  return (
    <AppContext.Provider value={app}>
      <div className="app-shell">
        <Nav view={route.view} />
        <main>{renderView()}</main>
        {browseRequest && <PlayerBrowser request={browseRequest} onClose={() => setBrowseRequest(null)} />}
      </div>
    </AppContext.Provider>
  );
}

export default App;
