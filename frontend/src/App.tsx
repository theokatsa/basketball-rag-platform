import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { AppContext } from './AppContext';
import type { AppData } from './AppContext';
import { Compare } from './components/Compare';
import { Directory } from './components/Directory';
import { CloseIcon } from './components/Icons';
import { Nav } from './components/Nav';
import { PlayerDetail } from './components/PlayerDetail';
import { Shortlist } from './components/Shortlist';
import { Explorer } from './pages/Explorer';
import { Form } from './pages/Form';
import { Home } from './pages/Home';
import { Lineup } from './pages/Lineup';
import { Report } from './pages/Report';
import { Scout } from './pages/Scout';
import { ShotLab } from './pages/ShotLab';
import { Team, Teams } from './pages/Teams';
import { TopPlayers } from './pages/TopPlayers';
import { YoungTalent } from './pages/YoungTalent';
import type { GameLog, PlayerDetailData, PlayerProfile, PlayerRecord, SeasonStat, ShotRecord, SimilarPlayerResult, View } from './types';
import { useDirectory } from './useDirectory';
import { loadStored, saveStored } from './utils';

const FAVORITES_KEY = 'basketball-scouting-favorites';
const HISTORY_KEY = 'basketball-scouting-history';
const GROUPS_KEY = 'basketball-scouting-groups';
const COMPARE_KEY = 'basketball-scouting-compare';
const MAX_COMPARE = 3;

type Route = { view: View; id?: number };
const PLAIN_VIEWS: View[] = ['home', 'players', 'top', 'teams', 'scout', 'explorer', 'shotlab', 'young', 'form', 'lineup', 'shortlist', 'compare'];
function parseHash(): Route {
  const [name, id] = window.location.hash.slice(1).split('/');
  if (id && /^\d+$/.test(id) && (name === 'player' || name === 'team' || name === 'report')) return { view: name, id: Number(id) };
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
  const [compareIds, setCompareIds] = useState<number[]>(() => loadStored<number[]>(COMPARE_KEY, []));
  useEffect(() => { saveStored(FAVORITES_KEY, favoriteIds); }, [favoriteIds]);
  useEffect(() => { saveStored(HISTORY_KEY, historyIds); }, [historyIds]);
  useEffect(() => { saveStored(GROUPS_KEY, groups); }, [groups]);
  useEffect(() => { saveStored(COMPARE_KEY, compareIds); }, [compareIds]);

  const loadPlayer = useCallback(async (playerId: number) => {
    const token = ++requestToken.current;
    setDetail(null);
    setDetailError(null);
    setDetailLoading(true);
    setHistoryIds((ids) => [playerId, ...ids.filter((id) => id !== playerId)].slice(0, 8));
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
        list<SimilarPlayerResult>('similar?limit=5'),
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
  const toggleCompare = useCallback((id: number) => setCompareIds((ids) => (ids.includes(id) ? ids.filter((v) => v !== id) : ids.length >= MAX_COMPARE ? ids : [...ids, id])), []);

  const byId = useMemo(() => new Map(dir.players.map((p) => [p.player_id, p])), [dir.players]);
  const app = useMemo<AppData>(() => ({ players: dir.players, totals: dir.totals, byId, loading: dir.loading, error: dir.error, favoriteIds, compareIds, historyIds, toggleFavorite, toggleCompare, open, go }), [dir.players, dir.totals, dir.loading, dir.error, byId, favoriteIds, compareIds, historyIds, toggleFavorite, toggleCompare, open, go]);
  const nameFor = (id: number) => byId.get(id)?.full_name ?? `Player ${id}`;
  const favoritePlayers = favoriteIds.map((id) => byId.get(id)).filter((p) => p != null);

  const renderView = (): ReactNode => {
    switch (route.view) {
      case 'home': return <Home />;
      case 'players': return <Directory dir={dir} favoriteIds={favoriteIds} compareIds={compareIds} onToggleFavorite={toggleFavorite} onToggleCompare={toggleCompare} onOpen={open} />;
      case 'top': return <TopPlayers />;
      case 'teams': return <Teams />;
      case 'team': return <Team key={route.id} id={route.id ?? 0} />;
      case 'scout': return <Scout />;
      case 'explorer': return <Explorer />;
      case 'shotlab': return <ShotLab />;
      case 'young': return <YoungTalent />;
      case 'form': return <Form />;
      case 'lineup': return <Lineup />;
      case 'report': return <Report key={route.id} id={route.id ?? 0} />;
      case 'shortlist': return <Shortlist favoritePlayers={favoritePlayers} groups={groups} setGroups={setGroups} compareIds={compareIds} onToggleFavorite={toggleFavorite} onToggleCompare={toggleCompare} onOpen={open} />;
      case 'compare': return <Compare ids={compareIds} players={dir.players} onRemove={toggleCompare} onOpen={open} onBack={goBack} />;
      case 'player': return <PlayerDetail key={route.id} detail={detail?.player.id === route.id ? detail : null} loading={detailLoading || detail?.player.id !== route.id} error={detailError} favorite={route.id != null && favoriteIds.includes(route.id)} comparing={route.id != null && compareIds.includes(route.id)} compareFull={compareIds.length >= MAX_COMPARE} nbaIdOf={(id) => byId.get(id)?.nba_player_id} onBack={goBack} onToggleFavorite={toggleFavorite} onToggleCompare={toggleCompare} onOpen={open} onReport={(id) => go('report', id)} />;
    }
  };
  const showTray = compareIds.length > 0 && !['compare', 'report', 'home', 'lineup', 'scout'].includes(route.view);

  return (
    <AppContext.Provider value={app}>
      <div className="app-shell">
        <Nav view={route.view} />
        <main>{renderView()}</main>
        {showTray && (
          <div className="compare-tray" role="region" aria-label="Comparison tray">
            <span>Compare</span>
            {compareIds.map((id) => <button type="button" key={id} className="tray-chip" onClick={() => toggleCompare(id)} aria-label={`Remove ${nameFor(id)} from comparison`}>{nameFor(id)}<CloseIcon /></button>)}
            <button type="button" className="nav-button" disabled={compareIds.length < 2} onClick={() => go('compare')}>{compareIds.length < 2 ? 'Pick one more' : `Compare ${compareIds.length}`}</button>
          </div>
        )}
      </div>
    </AppContext.Provider>
  );
}

export default App;
