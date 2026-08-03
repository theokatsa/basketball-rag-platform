import { FormEvent, useEffect, useMemo, useState } from 'react';

type PlayerDirectoryRow = {
  player_id: number;
  full_name: string;
  is_active: boolean;
  season: string | null;
  club: string | null;
  games_played: number | null;
  points: number | null;
  rebounds: number | null;
  assists: number | null;
};

type SimilarPlayerResult = {
  player_id: number;
  full_name: string;
  season: string;
  source_text: string;
  similarity: number;
  age: number | null;
  position: string | null;
  is_active: boolean;
};

type SortMode = 'name-asc' | 'name-desc' | 'id-asc' | 'id-desc';

type ActiveFilterMode = 'any' | 'true' | 'false';

type ReferencePlayerOption = {
  player_id: number;
  full_name: string;
};

type PositionOption = {
  position: string;
};

const PAGE_SIZE = 25;

function App() {
  const [players, setPlayers] = useState<PlayerDirectoryRow[]>([]);
  const [directoryQuery, setDirectoryQuery] = useState('');
  const [sortMode, setSortMode] = useState<SortMode>('name-asc');
  const [currentPage, setCurrentPage] = useState(1);
  const [loadingPlayers, setLoadingPlayers] = useState(true);
  const [playersError, setPlayersError] = useState<string | null>(null);

  const [referencePlayer, setReferencePlayer] = useState('Giannis');
  const [selectedReferencePlayerId, setSelectedReferencePlayerId] = useState<number | null>(null);
  const [referenceOptions, setReferenceOptions] = useState<ReferencePlayerOption[]>([]);
  const [showReferenceOptions, setShowReferenceOptions] = useState(false);
  const [season, setSeason] = useState('');
  const [limit, setLimit] = useState(8);
  const [minAge, setMinAge] = useState('');
  const [maxAge, setMaxAge] = useState('25');
  const [position, setPosition] = useState('');
  const [activeMode, setActiveMode] = useState<ActiveFilterMode>('any');
  const [positionOptions, setPositionOptions] = useState<string[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<SimilarPlayerResult[]>([]);

  useEffect(() => {
    const loadPlayers = async () => {
      try {
        const response = await fetch('/api/players/directory');
        if (!response.ok) {
          throw new Error('Unable to load players from API.');
        }
        const data = (await response.json()) as PlayerDirectoryRow[];
        setPlayers(data);
      } catch (err) {
        setPlayersError(err instanceof Error ? err.message : 'Unknown error while loading players.');
      } finally {
        setLoadingPlayers(false);
      }
    };

    const loadPositionOptions = async () => {
      try {
        const response = await fetch('/api/search/positions');
        if (!response.ok) {
          return;
        }
        const data = (await response.json()) as PositionOption[];
        setPositionOptions(data.map((item) => item.position));
      } catch {
        setPositionOptions([]);
      }
    };

    loadPlayers();
    loadPositionOptions();
  }, []);

  useEffect(() => {
    const term = referencePlayer.trim();
    if (term.length < 2) {
      setReferenceOptions([]);
      return;
    }

    const handle = setTimeout(async () => {
      try {
        const params = new URLSearchParams();
        params.set('q', term);
        params.set('limit', '8');

        const response = await fetch(`/api/search/reference-players?${params.toString()}`);
        if (!response.ok) {
          setReferenceOptions([]);
          return;
        }

        const data = (await response.json()) as ReferencePlayerOption[];
        setReferenceOptions(data);
      } catch {
        setReferenceOptions([]);
      }
    }, 180);

    return () => clearTimeout(handle);
  }, [referencePlayer]);

  const filteredPlayers = useMemo(() => {
    const term = directoryQuery.trim().toLowerCase();
    const searched = term
      ? players.filter((player) =>
          `${player.full_name} ${player.club ?? ''}`.toLowerCase().includes(term),
        )
      : players;

    return [...searched].sort((a, b) => {
      if (sortMode === 'name-asc') return a.full_name.localeCompare(b.full_name);
      if (sortMode === 'name-desc') return b.full_name.localeCompare(a.full_name);
      if (sortMode === 'id-asc') return a.player_id - b.player_id;
      return b.player_id - a.player_id;
    });
  }, [players, directoryQuery, sortMode]);

  const pageCount = Math.max(1, Math.ceil(filteredPlayers.length / PAGE_SIZE));

  useEffect(() => {
    setCurrentPage(1);
  }, [directoryQuery, sortMode]);

  const pagedPlayers = useMemo(() => {
    const safePage = Math.min(currentPage, pageCount);
    const start = (safePage - 1) * PAGE_SIZE;
    return filteredPlayers.slice(start, start + PAGE_SIZE);
  }, [currentPage, pageCount, filteredPlayers]);

  const toOptionalNumber = (value: string) => {
    const trimmed = value.trim();
    if (!trimmed) {
      return null;
    }

    const numeric = Number(trimmed);
    if (Number.isNaN(numeric)) {
      return null;
    }
    return numeric;
  };

  const handleHybridSearch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSearching(true);
    setSearchError(null);

    const payload: Record<string, unknown> = {
      limit,
    };

    const referenceTrimmed = referencePlayer.trim();

    if (!referenceTrimmed) {
      setSearching(false);
      setSearchError('Please provide a reference player name or id.');
      return;
    }

    if (selectedReferencePlayerId !== null) {
      payload.player_id = selectedReferencePlayerId;
    } else {
      payload.player_name = referenceTrimmed;
    }

    if (season.trim()) {
      payload.season = season.trim();
    }

    const minAgeNumber = toOptionalNumber(minAge);
    const maxAgeNumber = toOptionalNumber(maxAge);
    if (minAgeNumber !== null) payload.min_age = minAgeNumber;
    if (maxAgeNumber !== null) payload.max_age = maxAgeNumber;
    if (position.trim()) payload.position = position.trim();
    if (activeMode !== 'any') payload.is_active = activeMode === 'true';

    try {
      const response = await fetch('/api/search/similar-players', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const text = await response.text();
        try {
          const parsed = JSON.parse(text) as { detail?: string };
          throw new Error(parsed.detail || 'Hybrid search request failed.');
        } catch {
          throw new Error(text || 'Hybrid search request failed.');
        }
      }

      const data = (await response.json()) as SimilarPlayerResult[];
      setSearchResults(data);
    } catch (err) {
      setSearchResults([]);
      setSearchError(err instanceof Error ? err.message : 'Unknown search error.');
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="app-shell">
      <div className="background-grid" aria-hidden="true" />

      <header className="hero">
        <p className="eyebrow">Week 7 · Hybrid Search</p>
        <h1>Scouting Console</h1>
        <p className="hero-copy">
          Browse player data and combine vector similarity with SQL filters in one workflow.
        </p>
      </header>

      <main className="layout-grid">
        <section className="panel panel-directory">
          <div className="panel-header">
            <h2>Player Directory</h2>
            <p>{filteredPlayers.length.toLocaleString()} players</p>
          </div>

          <div className="toolbar">
            <input
              value={directoryQuery}
              onChange={(event) => setDirectoryQuery(event.target.value)}
              placeholder="Search by name"
              className="control-input"
            />

            <select
              value={sortMode}
              onChange={(event) => setSortMode(event.target.value as SortMode)}
              className="control-input"
            >
              <option value="name-asc">Name A-Z</option>
              <option value="name-desc">Name Z-A</option>
              <option value="id-asc">ID low-high</option>
              <option value="id-desc">ID high-low</option>
            </select>
          </div>

          {loadingPlayers && <p className="status">Loading players...</p>}
          {playersError && <p className="status error">{playersError}</p>}

          {!loadingPlayers && !playersError && (
            <>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Club</th>
                      <th>PTS</th>
                      <th>REB</th>
                      <th>AST</th>
                      <th>GP</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pagedPlayers.map((player, index) => (
                      <tr key={player.player_id} style={{ animationDelay: `${index * 25}ms` }}>
                        <td>{player.full_name}</td>
                        <td>{player.club ?? '-'}</td>
                        <td>{player.points?.toFixed(1) ?? '-'}</td>
                        <td>{player.rebounds?.toFixed(1) ?? '-'}</td>
                        <td>{player.assists?.toFixed(1) ?? '-'}</td>
                        <td>{player.games_played ?? '-'}</td>
                        <td>
                          <span className={`pill ${player.is_active ? 'active' : 'inactive'}`}>
                            {player.is_active ? 'Active' : 'Inactive'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="pagination">
                <button
                  type="button"
                  className="nav-button"
                  disabled={currentPage <= 1}
                  onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
                >
                  Prev
                </button>
                <span>
                  Page {Math.min(currentPage, pageCount)} / {pageCount}
                </span>
                <button
                  type="button"
                  className="nav-button"
                  disabled={currentPage >= pageCount}
                  onClick={() => setCurrentPage((page) => Math.min(pageCount, page + 1))}
                >
                  Next
                </button>
              </div>
            </>
          )}
        </section>

        <section className="panel panel-search">
          <div className="panel-header">
            <h2>Hybrid Similarity Search</h2>
            <p>Vector + SQL filters</p>
          </div>

          <form className="search-form" onSubmit={handleHybridSearch}>
            <label>
              Reference player
              <input
                className="control-input"
                value={referencePlayer}
                onFocus={() => setShowReferenceOptions(true)}
                onBlur={() => setTimeout(() => setShowReferenceOptions(false), 140)}
                onChange={(event) => {
                  setReferencePlayer(event.target.value);
                  setSelectedReferencePlayerId(null);
                  setShowReferenceOptions(true);
                }}
                placeholder="Type a player name"
              />
              {showReferenceOptions && referenceOptions.length > 0 && (
                <div className="autocomplete-list" role="listbox" aria-label="Reference player suggestions">
                  {referenceOptions.map((option) => (
                    <button
                      type="button"
                      key={option.player_id}
                      className="autocomplete-item"
                      onMouseDown={() => {
                        setReferencePlayer(option.full_name);
                        setSelectedReferencePlayerId(option.player_id);
                        setShowReferenceOptions(false);
                      }}
                    >
                      {option.full_name}
                    </button>
                  ))}
                </div>
              )}
            </label>

            <div className="grid-2">
              <label>
                Season
                <input
                  className="control-input"
                  value={season}
                  onChange={(event) => setSeason(event.target.value)}
                  placeholder="Any season (e.g. 2024-25)"
                />
              </label>
              <label>
                Results count (Top-K nearest players)
                <input
                  className="control-input"
                  type="number"
                  min={1}
                  max={50}
                  value={limit}
                  onChange={(event) => setLimit(Math.max(1, Math.min(50, Number(event.target.value) || 1)))}
                />
                <small className="help-text">How many similar players to return.</small>
              </label>
            </div>

            <div className="grid-3">
              <label>
                Min age
                <input
                  className="control-input"
                  type="number"
                  min={0}
                  value={minAge}
                  onChange={(event) => setMinAge(event.target.value)}
                  placeholder="Any"
                />
              </label>

              <label>
                Max age
                <input
                  className="control-input"
                  type="number"
                  min={0}
                  value={maxAge}
                  onChange={(event) => setMaxAge(event.target.value)}
                  placeholder="Any"
                />
              </label>

              <label>
                Position
                <select
                  className="control-input"
                  value={position}
                  onChange={(event) => setPosition(event.target.value)}
                >
                  <option value="">Any</option>
                  {positionOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <label>
              Active status
              <select
                className="control-input"
                value={activeMode}
                onChange={(event) => setActiveMode(event.target.value as ActiveFilterMode)}
              >
                <option value="any">Any</option>
                <option value="true">Active only</option>
                <option value="false">Inactive only</option>
              </select>
            </label>

            <button type="submit" className="submit-button" disabled={searching}>
              {searching ? 'Searching...' : 'Run hybrid search'}
            </button>
          </form>

          {searchError && <p className="status error">{searchError}</p>}

          {!searchError && searchResults.length > 0 && (
            <div className="results-list">
              {searchResults.map((result, index) => (
                <article
                  className="result-card"
                  key={`${result.player_id}-${result.season}-${index}`}
                  style={{ animationDelay: `${index * 55}ms` }}
                >
                  <div className="result-head">
                    <h3>{result.full_name}</h3>
                    <span className="score">{(result.similarity * 100).toFixed(1)}%</span>
                  </div>
                  <div className="meta-row">
                    <span>Season: {result.season}</span>
                    <span>Age: {result.age ?? 'N/A'}</span>
                    <span>Position: {result.position ?? 'N/A'}</span>
                    <span>{result.is_active ? 'Active' : 'Inactive'}</span>
                  </div>
                </article>
              ))}
            </div>
          )}

          {!searchError && !searching && searchResults.length === 0 && (
            <p className="status">No similarity results yet. Run a hybrid search.</p>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;
