import { FormEvent, useEffect, useMemo, useState } from 'react';

type PlayerDirectoryRow = { player_id: number; nba_player_id: number; full_name: string; is_active: boolean; season: string | null; club: string | null; club_full_name: string | null; club_team_id: number | null; games_played: number | null; minutes: number | null; points: number | null; rebounds: number | null; assists: number | null; steals: number | null; blocks: number | null; turnovers: number | null; field_goal_pct: number | null; three_point_pct: number | null; free_throw_pct: number | null };
type SeasonStat = { player_id: number; season: string; team_id: number | null; position: string | null; games_played: number; minutes: number; points: number; rebounds: number; assists: number; steals: number; blocks: number; turnovers: number; field_goal_pct: number | null; three_point_pct: number | null; free_throw_pct: number | null; points_percentile: number | null; rebounds_percentile: number | null; assists_percentile: number | null; steals_percentile: number | null; blocks_percentile: number | null; field_goal_percentile: number | null; position_points_percentile: number | null; position_rebounds_percentile: number | null; position_assists_percentile: number | null; position_steals_percentile: number | null; position_blocks_percentile: number | null; position_field_goal_percentile: number | null; points_rank: number | null; rebounds_rank: number | null; assists_rank: number | null; steals_rank: number | null; blocks_rank: number | null; turnovers_rank: number | null; field_goal_rank: number | null; three_point_rank: number | null; free_throw_rank: number | null };
type PlayerProfile = { position: string | null; age: number | null; height: string | null; weight: string | null };
type GameLog = { player_id: number; game_id: number; season: string; minutes: string; points: number; rebounds: number; assists: number; steals: number; blocks: number; turnovers: number; field_goals_made: number; field_goals_attempted: number; three_pointers_made: number; three_pointers_attempted: number; free_throws_made: number; free_throws_attempted: number; plus_minus: number | null; nba_game_id: string | null; game_date: string | null };
type ShotRecord = { player_id: number; nba_game_id: string; season: string; period: number; minutes_remaining: number; seconds_remaining: number; action_type: string; shot_type: string; shot_zone_basic: string; shot_zone_area: string; shot_zone_range: string; shot_distance: number; loc_x: number; loc_y: number; shot_made: boolean; game_date: string | null; matchup: string };
type PlayerRecord = { id: number; nba_player_id: number; full_name: string; first_name: string; last_name: string; is_active: boolean };
type SimilarPlayerResult = { player_id: number; full_name: string; season: string; source_text: string; similarity: number; age: number | null; position: string | null; is_active: boolean };
type SortKey = 'name' | 'club' | 'points' | 'rebounds' | 'assists' | 'games_played' | 'minutes' | 'steals' | 'blocks' | 'turnovers' | 'field_goal_pct' | 'three_point_pct' | 'free_throw_pct';
type SortDirection = 'asc' | 'desc';
type ActiveFilterMode = 'any' | 'true' | 'false';
type ReferencePlayerOption = { player_id: number; full_name: string };
type RagSource = { player_id: number; full_name: string; season: string; source_text: string; similarity: number };
type AskResponse = { answer: string; provider: string; model: string; sources: RagSource[] };
type View = 'directory' | 'shortlist' | 'player';
type DirectorySnapshot = { query: string; club: string; sortKey: SortKey; sortDirection: SortDirection; page: number };
type PlayerDetail = { player: PlayerRecord; profile: PlayerProfile; stats: SeasonStat[]; logs: GameLog[]; shots: ShotRecord[]; similar: SimilarPlayerResult[] };
type DirectoryStatFilters = { points: number; rebounds: number; assists: number; minutes: number; steals: number; blocks: number; turnovers: number; field_goal_pct: number; three_point_pct: number; free_throw_pct: number };

const PAGE_SIZE = 25;
const FAVORITES_KEY = 'basketball-scouting-favorites';
const HISTORY_KEY = 'basketball-scouting-history';
const GROUPS_KEY = 'basketball-scouting-groups';

function App() {
  const [players, setPlayers] = useState<PlayerDirectoryRow[]>([]);
  const [directoryQuery, setDirectoryQuery] = useState('');
  const [clubFilter, setClubFilter] = useState('');
  const [statFilters, setStatFilters] = useState<DirectoryStatFilters>({ points: 0, rebounds: 0, assists: 0, minutes: 0, steals: 0, blocks: 0, turnovers: 0, field_goal_pct: 0, three_point_pct: 0, free_throw_pct: 0 });
  const [showStatFilters, setShowStatFilters] = useState(false);
  const [showAdvancedStats, setShowAdvancedStats] = useState(false);
  const [advancedLogs, setAdvancedLogs] = useState<Record<number, GameLog[]>>({});
  const [advancedLoading, setAdvancedLoading] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>('name');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [currentPage, setCurrentPage] = useState(1);
  const [loadingPlayers, setLoadingPlayers] = useState(true);
  const [playersError, setPlayersError] = useState<string | null>(null);
  const [view, setView] = useState<View>('directory');
  const [detail, setDetail] = useState<PlayerDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [directorySnapshot, setDirectorySnapshot] = useState<DirectorySnapshot>({ query: '', club: '', sortKey: 'name', sortDirection: 'asc', page: 1 });
  const [favoriteIds, setFavoriteIds] = useState<number[]>(() => JSON.parse(localStorage.getItem(FAVORITES_KEY) || '[]') as number[]);
  const [historyIds, setHistoryIds] = useState<number[]>(() => JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]') as number[]);
  const [groups, setGroups] = useState<Record<string, number[]>>(() => JSON.parse(localStorage.getItem(GROUPS_KEY) || '{}') as Record<string, number[]>);
  const [newGroupName, setNewGroupName] = useState('');
  const [activeGroup, setActiveGroup] = useState('All saved');

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
  const [ragQuestion, setRagQuestion] = useState('Which young players have a playing style similar to Giannis?');
  const [ragSeason, setRagSeason] = useState('');
  const [asking, setAsking] = useState(false);
  const [ragError, setRagError] = useState<string | null>(null);
  const [ragResponse, setRagResponse] = useState<AskResponse | null>(null);

  useEffect(() => {
    const loadPlayers = async () => {
      try {
        const response = await fetch('/api/players/directory');
        if (!response.ok) throw new Error('Unable to load players from API.');
        setPlayers((await response.json()) as PlayerDirectoryRow[]);
      } catch (err) {
        setPlayersError(err instanceof Error ? err.message : 'Unknown error while loading players.');
      } finally { setLoadingPlayers(false); }
    };
    const loadPositions = async () => {
      try {
        const response = await fetch('/api/search/positions');
        if (response.ok) setPositionOptions(((await response.json()) as { position: string }[]).map((item) => item.position));
      } catch { setPositionOptions([]); }
    };
    loadPlayers();
    loadPositions();
  }, []);

  useEffect(() => {
    localStorage.setItem(FAVORITES_KEY, JSON.stringify(favoriteIds));
  }, [favoriteIds]);
  useEffect(() => {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(historyIds));
  }, [historyIds]);
  useEffect(() => {
    localStorage.setItem(GROUPS_KEY, JSON.stringify(groups));
  }, [groups]);
  useEffect(() => {
    const handlePopState = () => {
      setView('directory');
      setDetail(null);
      setDirectoryQuery(directorySnapshot.query);
      setClubFilter(directorySnapshot.club);
      setSortKey(directorySnapshot.sortKey);
      setSortDirection(directorySnapshot.sortDirection);
      setCurrentPage(directorySnapshot.page);
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [directorySnapshot]);

  useEffect(() => {
    if (view !== 'player' || !detail?.stats[0]) return;
    const stat = detail.stats[0];
    const statsList = document.querySelector('.stats-list');
    if (statsList) {
      statsList.innerHTML = detail.stats.map((seasonStat) => `<div class="season-row"><strong>${seasonStat.season}</strong><span>${seasonStat.points.toFixed(1)} PTS</span><span>${seasonStat.rebounds.toFixed(1)} REB</span><span>${seasonStat.assists.toFixed(1)} AST</span><span>${seasonStat.steals.toFixed(1)} STL</span><span>${seasonStat.blocks.toFixed(1)} BLK</span><span>${seasonStat.turnovers.toFixed(1)} TOV</span><span>${seasonStat.minutes.toFixed(1)} MIN</span><span>${seasonStat.field_goal_pct == null ? '-' : `${(seasonStat.field_goal_pct * 100).toFixed(1)} FG%`}</span><span>${seasonStat.three_point_pct == null ? '-' : `${(seasonStat.three_point_pct * 100).toFixed(1)} 3P%`}</span><span>${seasonStat.free_throw_pct == null ? '-' : `${(seasonStat.free_throw_pct * 100).toFixed(1)} FT%`}</span></div>`).join('');
      detail.stats.forEach((seasonStat, index) => {
        const row = statsList.children[index];
        const ranks = [seasonStat.points_rank, seasonStat.rebounds_rank, seasonStat.assists_rank, seasonStat.steals_rank, seasonStat.blocks_rank, seasonStat.turnovers_rank, null, seasonStat.field_goal_rank, seasonStat.three_point_rank, seasonStat.free_throw_rank];
        Array.from(row?.querySelectorAll('span') ?? []).forEach((span, metricIndex) => { span.textContent += ` ${rankLabel(ranks[metricIndex])}`; });
      });
    }
    const mark = document.querySelector('.detail-mark') as HTMLElement | null;
    if (mark) mark.style.backgroundImage = `url(${playerImage(detail.player.nba_player_id)})`;
    const detailGrid = document.querySelector('.detail-grid');
    if (!detailGrid) return;
    const oldRadar = detailGrid.querySelector('.radar-panel');
    oldRadar?.remove();
    const allMetrics: Array<[string, number | null]> = [
      ['PTS', stat.points_percentile], ['REB', stat.rebounds_percentile], ['AST', stat.assists_percentile],
      ['STL', stat.steals_percentile], ['BLK', stat.blocks_percentile], ['FG%', stat.field_goal_percentile],
    ];
    const positionMetrics: Array<[string, number | null]> = [
      ['PTS', stat.position_points_percentile], ['REB', stat.position_rebounds_percentile], ['AST', stat.position_assists_percentile],
      ['STL', stat.position_steals_percentile], ['BLK', stat.position_blocks_percentile], ['FG%', stat.position_field_goal_percentile],
    ];
    const metrics = detail.profile.position ? positionMetrics : allMetrics;
    const center = 130;
    const radius = 92;
    const points = metrics.map(([, percentile], index) => {
      const angle = (Math.PI * 2 * index) / metrics.length - Math.PI / 2;
      const value = (1 - (percentile ?? 1)) * radius;
      return `${center + Math.cos(angle) * value},${center + Math.sin(angle) * value}`;
    }).join(' ');
    const gridPoints = [1, .75, .5, .25].map((scale) => metrics.map(([,], index) => {
      const angle = (Math.PI * 2 * index) / metrics.length - Math.PI / 2;
      return `${center + Math.cos(angle) * radius * scale},${center + Math.sin(angle) * radius * scale}`;
    }).join(' '));
    const average = metrics.reduce((sum, [, percentile]) => sum + (1 - (percentile ?? 1)), 0) / metrics.length;
    const tone = average >= .95 ? '#2f9e44' : average >= .75 ? '#167c78' : '#ef5b32';
    const radar = document.createElement('section');
    radar.className = 'panel radar-panel';
    radar.innerHTML = `<div class="panel-header"><div><p class="section-kicker">Top-percentile view / ${stat.season}</p><h2>Player shape</h2><small>${detail.profile.position ? `${detail.profile.position} comparison` : 'All positions comparison'}</small></div><span class="radar-badge" style="background:${tone}">Top ${Math.round((1 - average) * 100)}% avg</span></div><div class="radar-wrap"><svg viewBox="0 0 260 260" role="img" aria-label="Percentile radar chart">${gridPoints.map((grid) => `<polygon points="${grid}" fill="none" stroke="rgba(149,174,157,.35)" />`).join('')}<polygon points="${points}" fill="${tone}33" stroke="${tone}" stroke-width="3" />${metrics.map(([label, percentile], index) => { const angle = (Math.PI * 2 * index) / metrics.length - Math.PI / 2; const x = center + Math.cos(angle) * 112; const y = center + Math.sin(angle) * 112; return `<text x="${x}" y="${y}" text-anchor="middle" dominant-baseline="middle">${label} Top ${Math.round((percentile ?? 1) * 100)}%</text>`; }).join('')}</svg></div><p class="radar-note">Top 0% is best. Green is top 5%; teal is top 25%; orange is below that band.</p>`;
    const radarSvg = radar.querySelector('svg');
    metrics.forEach(([, percentile], index) => {
      if (!radarSvg) return;
      const angle = (Math.PI * 2 * index) / metrics.length - Math.PI / 2;
      const point = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      const value = (1 - (percentile ?? 1)) * radius;
      point.setAttribute('cx', String(center + Math.cos(angle) * value));
      point.setAttribute('cy', String(center + Math.sin(angle) * value));
      point.setAttribute('r', '4');
      point.setAttribute('fill', (percentile ?? 1) <= .05 ? '#2f9e44' : (percentile ?? 1) <= .25 ? '#167c78' : '#ef5b32');
      point.setAttribute('stroke', '#fffaf0');
      point.setAttribute('stroke-width', '2');
      radarSvg.appendChild(point);
    });
    detailGrid.appendChild(radar);
    const overallPoints = allMetrics.map(([, percentile], index) => {
      const angle = (Math.PI * 2 * index) / allMetrics.length - Math.PI / 2;
      const value = (1 - (percentile ?? 1)) * radius;
      return `${center + Math.cos(angle) * value},${center + Math.sin(angle) * value}`;
    }).join(' ');
    const overallAverage = allMetrics.reduce((sum, [, percentile]) => sum + (1 - (percentile ?? 1)), 0) / allMetrics.length;
    const overallTone = overallAverage >= .95 ? '#2f9e44' : overallAverage >= .75 ? '#167c78' : '#ef5b32';
    const overallRadar = document.createElement('section');
    overallRadar.className = 'panel radar-panel';
    overallRadar.innerHTML = `<div class="panel-header"><div><p class="section-kicker">Top-percentile view / ${stat.season}</p><h2>All-player shape</h2><small>Compared with every player</small></div><span class="radar-badge" style="background:${overallTone}">Top ${Math.round((1 - overallAverage) * 100)}% avg</span></div><div class="radar-wrap"><svg viewBox="0 0 260 260" role="img" aria-label="All-player percentile radar chart">${gridPoints.map((grid) => `<polygon points="${grid}" fill="none" stroke="rgba(149,174,157,.35)" />`).join('')}<polygon points="${overallPoints}" fill="${overallTone}33" stroke="${overallTone}" stroke-width="3" />${allMetrics.map(([label, percentile], index) => { const angle = (Math.PI * 2 * index) / allMetrics.length - Math.PI / 2; const x = center + Math.cos(angle) * 112; const y = center + Math.sin(angle) * 112; return `<text x="${x}" y="${y}" text-anchor="middle" dominant-baseline="middle">${label} Top ${Math.round((percentile ?? 1) * 100)}%</text>`; }).join('')}</svg></div><p class="radar-note">This view uses the full player population. Top 0% is best.</p>`;
    detailGrid.appendChild(overallRadar);
    const recordsPanel = document.createElement('section');
    recordsPanel.className = 'panel detail-records-panel';
    recordsPanel.innerHTML = `<div class="panel-header"><div><p class="section-kicker">Raw performance data</p><h2>Game logs</h2></div><span class="count-label">${detail.logs.length} games</span></div><div class="detail-records-scroll"><table class="detail-records-table"><thead><tr><th>Date</th><th>MIN</th><th>PTS</th><th>REB</th><th>AST</th><th>STL</th><th>BLK</th><th>TOV</th><th>FG</th><th>3P</th><th>FT</th><th>+/-</th></tr></thead><tbody>${detail.logs.map((log) => `<tr><td>${log.game_date ?? '-'}</td><td>${log.minutes}</td><td>${log.points}</td><td>${log.rebounds}</td><td>${log.assists}</td><td>${log.steals}</td><td>${log.blocks}</td><td>${log.turnovers}</td><td>${log.field_goals_made}/${log.field_goals_attempted}</td><td>${log.three_pointers_made}/${log.three_pointers_attempted}</td><td>${log.free_throws_made}/${log.free_throws_attempted}</td><td>${log.plus_minus ?? '-'}</td></tr>`).join('')}</tbody></table></div><div class="panel-header records-subheader"><div><p class="section-kicker">Shot-level evidence</p><h2>Individual shots</h2></div><span class="count-label">${detail.shots.length} attempts</span></div><div class="detail-records-scroll"><table class="detail-records-table"><thead><tr><th>Date</th><th>Result</th><th>Distance</th><th>Zone</th><th>Range</th><th>Action</th><th>Period</th><th>Clock</th><th>Matchup</th></tr></thead><tbody>${detail.shots.map((shot) => `<tr><td>${shot.game_date ?? '-'}</td><td><span class="shot-result ${shot.shot_made ? 'made' : 'missed'}">${shot.shot_made ? 'Made' : 'Missed'}</span></td><td>${shot.shot_distance} ft</td><td>${shot.shot_zone_basic}</td><td>${shot.shot_zone_range}</td><td>${shot.action_type}</td><td>${shot.period}</td><td>${shot.minutes_remaining}:${String(shot.seconds_remaining).padStart(2, '0')}</td><td>${shot.matchup}</td></tr>`).join('')}</tbody></table></div>`;
    detailGrid.appendChild(recordsPanel);
    return () => { radar.remove(); overallRadar.remove(); recordsPanel.remove(); };
  }, [detail, view]);

  useEffect(() => {
    const term = referencePlayer.trim();
    if (term.length < 2) { setReferenceOptions([]); return; }
    const handle = setTimeout(async () => {
      try {
        const response = await fetch(`/api/search/reference-players?q=${encodeURIComponent(term)}&limit=8`);
        setReferenceOptions(response.ok ? ((await response.json()) as ReferencePlayerOption[]) : []);
      } catch { setReferenceOptions([]); }
    }, 180);
    return () => clearTimeout(handle);
  }, [referencePlayer]);

  const filteredPlayers = useMemo(() => {
    const term = directoryQuery.trim().toLowerCase();
    const searched = players.filter((player) => {
      const matchesName = !term || player.full_name.toLowerCase().includes(term);
      const meetsStats = Object.entries(statFilters).every(([key, minimum]) => (player[key as keyof PlayerDirectoryRow] as number | null ?? 0) >= minimum);
      return matchesName && (!clubFilter || player.club_full_name === clubFilter) && meetsStats;
    });
    return [...searched].sort((a, b) => {
      const left = sortKey === 'name' ? a.full_name : sortKey === 'club' ? (a.club_full_name ?? '') : (a[sortKey] ?? -Infinity);
      const right = sortKey === 'name' ? b.full_name : sortKey === 'club' ? (b.club_full_name ?? '') : (b[sortKey] ?? -Infinity);
      const result = typeof left === 'string' ? left.localeCompare(right as string) : (left as number) - (right as number);
      return sortDirection === 'asc' ? result : -result;
    });
  }, [players, directoryQuery, clubFilter, statFilters, sortKey, sortDirection]);
  const pageCount = Math.max(1, Math.ceil(filteredPlayers.length / PAGE_SIZE));
  const pagedPlayers = useMemo(() => filteredPlayers.slice((Math.min(currentPage, pageCount) - 1) * PAGE_SIZE, Math.min(currentPage, pageCount) * PAGE_SIZE), [currentPage, pageCount, filteredPlayers]);
  const historyPlayers = historyIds.map((id) => players.find((player) => player.player_id === id)).filter((player): player is PlayerDirectoryRow => Boolean(player));
  const favoritePlayers = favoriteIds.map((id) => players.find((player) => player.player_id === id)).filter((player): player is PlayerDirectoryRow => Boolean(player));
  const clubOptions = [...new Set(players.map((player) => player.club_full_name).filter((club): club is string => Boolean(club)))].sort();
  const groupNames = Object.keys(groups);

  useEffect(() => { setCurrentPage(1); }, [directoryQuery, clubFilter, statFilters, sortKey, sortDirection]);

  const toggleFavorite = (playerId: number) => setFavoriteIds((ids) => ids.includes(playerId) ? ids.filter((id) => id !== playerId) : [playerId, ...ids]);
  const sortBy = (key: SortKey) => {
    if (sortKey === key) setSortDirection((direction) => direction === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDirection('asc'); }
  };
  const updateStatFilter = (key: keyof DirectoryStatFilters, value: number) => setStatFilters((filters) => ({ ...filters, [key]: value }));
  const resetStatFilters = () => setStatFilters({ points: 0, rebounds: 0, assists: 0, minutes: 0, steals: 0, blocks: 0, turnovers: 0, field_goal_pct: 0, three_point_pct: 0, free_throw_pct: 0 });
  const loadAdvancedStats = async () => {
    setShowAdvancedStats(true);
    setAdvancedLoading(true);
    const entries = await Promise.all(pagedPlayers.map(async (player) => {
      const response = await fetch(`/api/players/${player.player_id}/game-logs`);
      return [player.player_id, response.ok ? await response.json() as GameLog[] : []] as const;
    }));
    setAdvancedLogs((current) => ({ ...current, ...Object.fromEntries(entries) }));
    setAdvancedLoading(false);
  };
  useEffect(() => {
    const tableElement = document.querySelector('.panel-directory > .table-wrap table');
    if (!tableElement) return;
    tableElement.querySelectorAll('.advanced-column').forEach((cell) => cell.remove());
    if (!showAdvancedStats || advancedLoading) return;
    const headerRow = tableElement.querySelector('thead tr');
    const favoriteHeader = headerRow?.lastElementChild;
    const favoriteCells = Array.from(tableElement.querySelectorAll('tbody tr')).map((row) => row.lastElementChild).filter((cell): cell is Element => Boolean(cell));
    favoriteHeader?.remove();
    favoriteCells.forEach((cell) => cell.remove());
    const headers = ['Total MIN', 'Total PTS', 'Total REB', 'Total AST', 'Total STL', 'Total BLK', 'Total TOV', 'FG made/att', '3P made/att', 'FT made/att', 'Total +/-'];
    headers.forEach((label) => { const cell = document.createElement('th'); cell.className = 'advanced-column'; cell.textContent = label; headerRow?.appendChild(cell); });
    tableElement.querySelectorAll('tbody tr').forEach((row, index) => {
      const player = pagedPlayers[index];
      const logs = advancedLogs[player?.player_id] ?? [];
      const total = logs.reduce((sum, log) => ({ minutes: sum.minutes + Number(log.minutes || 0), points: sum.points + log.points, rebounds: sum.rebounds + log.rebounds, assists: sum.assists + log.assists, steals: sum.steals + log.steals, blocks: sum.blocks + log.blocks, turnovers: sum.turnovers + log.turnovers, fieldGoalsMade: sum.fieldGoalsMade + log.field_goals_made, fieldGoalsAttempted: sum.fieldGoalsAttempted + log.field_goals_attempted, threesMade: sum.threesMade + log.three_pointers_made, threesAttempted: sum.threesAttempted + log.three_pointers_attempted, freeThrowsMade: sum.freeThrowsMade + log.free_throws_made, freeThrowsAttempted: sum.freeThrowsAttempted + log.free_throws_attempted, plusMinus: sum.plusMinus + (log.plus_minus ?? 0) }), { minutes: 0, points: 0, rebounds: 0, assists: 0, steals: 0, blocks: 0, turnovers: 0, fieldGoalsMade: 0, fieldGoalsAttempted: 0, threesMade: 0, threesAttempted: 0, freeThrowsMade: 0, freeThrowsAttempted: 0, plusMinus: 0 });
      [total.minutes.toFixed(1), total.points, total.rebounds, total.assists, total.steals, total.blocks, total.turnovers, `${total.fieldGoalsMade}/${total.fieldGoalsAttempted}`, `${total.threesMade}/${total.threesAttempted}`, `${total.freeThrowsMade}/${total.freeThrowsAttempted}`, total.plusMinus].forEach((value) => { const cell = document.createElement('td'); cell.className = 'advanced-column'; cell.textContent = String(value); row.appendChild(cell); });
    });
    if (favoriteHeader) headerRow?.appendChild(favoriteHeader);
    tableElement.querySelectorAll('tbody tr').forEach((row, index) => { if (favoriteCells[index]) row.appendChild(favoriteCells[index]); });
  }, [showAdvancedStats, advancedLoading, advancedLogs, pagedPlayers]);
  useEffect(() => {
    if (showAdvancedStats) void loadAdvancedStats();
  }, [showAdvancedStats, currentPage, pageCount, directoryQuery, clubFilter, statFilters, sortKey, sortDirection]);
  const advancedTotalsTable = <div className="advanced-log-wrap"><table className="advanced-log-table"><thead><tr><th>Player</th><th>Games</th><th>MIN</th><th>PTS</th><th>REB</th><th>AST</th><th>STL</th><th>BLK</th><th>TOV</th><th>FG</th><th>3P</th><th>FT</th><th>+/-</th></tr></thead><tbody>{pagedPlayers.map((player) => { const logs = advancedLogs[player.player_id] ?? []; const total = logs.reduce((sum, log) => ({ minutes: sum.minutes + Number(log.minutes || 0), points: sum.points + log.points, rebounds: sum.rebounds + log.rebounds, assists: sum.assists + log.assists, steals: sum.steals + log.steals, blocks: sum.blocks + log.blocks, turnovers: sum.turnovers + log.turnovers, field_goals_made: sum.field_goals_made + log.field_goals_made, field_goals_attempted: sum.field_goals_attempted + log.field_goals_attempted, three_pointers_made: sum.three_pointers_made + log.three_pointers_made, three_pointers_attempted: sum.three_pointers_attempted + log.three_pointers_attempted, free_throws_made: sum.free_throws_made + log.free_throws_made, free_throws_attempted: sum.free_throws_attempted + log.free_throws_attempted, plus_minus: sum.plus_minus + (log.plus_minus ?? 0) }), { minutes: 0, points: 0, rebounds: 0, assists: 0, steals: 0, blocks: 0, turnovers: 0, field_goals_made: 0, field_goals_attempted: 0, three_pointers_made: 0, three_pointers_attempted: 0, free_throws_made: 0, free_throws_attempted: 0, plus_minus: 0 }); return <tr key={player.player_id}><td>{playerButton(player)}</td><td>{logs.length}</td><td>{total.minutes.toFixed(1)}</td><td>{total.points}</td><td>{total.rebounds}</td><td>{total.assists}</td><td>{total.steals}</td><td>{total.blocks}</td><td>{total.turnovers}</td><td>{total.field_goals_made}/{total.field_goals_attempted}</td><td>{total.three_pointers_made}/{total.three_pointers_attempted}</td><td>{total.free_throws_made}/{total.free_throws_attempted}</td><td>{total.plus_minus}</td></tr>; })}</tbody></table></div>;
  void advancedTotalsTable;
  const sortIndicator = (_key: SortKey) => '';
  const createGroup = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const name = newGroupName.trim();
    if (!name || groups[name]) return;
    setGroups((current) => ({ ...current, [name]: [] }));
    setNewGroupName('');
    setActiveGroup(name);
  };
  const assignToGroup = (playerId: number, groupName: string) => {
    if (!groupName) return;
    setGroups((current) => ({ ...current, [groupName]: [...new Set([...(current[groupName] ?? []), playerId])] }));
  };
  const teamLogo = (teamId: number | null) => teamId ? `https://cdn.nba.com/logos/nba/${teamId}/primary/L/logo.svg` : null;
  function playerImage(nbaPlayerId: number) { return `https://cdn.nba.com/headshots/nba/latest/1040x760/${nbaPlayerId}.png`; }
  const rankLabel = (rank: number | null) => {
    if (rank == null) return '';
    const suffix = rank % 100 >= 11 && rank % 100 <= 13 ? 'th' : rank % 10 === 1 ? 'st' : rank % 10 === 2 ? 'nd' : rank % 10 === 3 ? 'rd' : 'th';
    return `(${rank}${suffix})`;
  };
  const openPlayer = async (playerId: number) => {
    setDirectorySnapshot({ query: directoryQuery, club: clubFilter, sortKey, sortDirection, page: currentPage });
    setView('player');
    setDetail(null);
    setDetailError(null);
    setDetailLoading(true);
    setHistoryIds((ids) => [playerId, ...ids.filter((id) => id !== playerId)].slice(0, 8));
    window.history.pushState({ view: 'player', playerId }, '', `#player/${playerId}`);
    try {
      const [playerResponse, profileResponse, statsResponse, logsResponse, shotsResponse, similarResponse] = await Promise.all([
        fetch(`/api/players/${playerId}`),
        fetch(`/api/players/${playerId}/profile`),
        fetch(`/api/players/${playerId}/season-stats`),
        fetch(`/api/players/${playerId}/game-logs`),
        fetch(`/api/players/${playerId}/shots`),
        fetch(`/api/players/${playerId}/similar?limit=5`),
      ]);
      if (!playerResponse.ok || !statsResponse.ok) throw new Error('Unable to load this player profile.');
      setDetail({ player: await playerResponse.json() as PlayerRecord, profile: profileResponse.ok ? await profileResponse.json() as PlayerProfile : { position: null, age: null, height: null, weight: null }, stats: await statsResponse.json() as SeasonStat[], logs: logsResponse.ok ? await logsResponse.json() as GameLog[] : [], shots: shotsResponse.ok ? await shotsResponse.json() as ShotRecord[] : [], similar: similarResponse.ok ? await similarResponse.json() as SimilarPlayerResult[] : [] });
    } catch (err) { setDetailError(err instanceof Error ? err.message : 'Unable to load this player profile.'); }
    finally { setDetailLoading(false); }
  };
  const goBack = () => { if (window.history.length > 1) window.history.back(); else { setView('directory'); } };
  const openShortlist = () => { setView('shortlist'); window.history.pushState({ view: 'shortlist' }, '', '#shortlist'); };
  const toOptionalNumber = (value: string) => { const trimmed = value.trim(); if (!trimmed) return null; const numeric = Number(trimmed); return Number.isNaN(numeric) ? null : numeric; };

  const handleHybridSearch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setSearching(true); setSearchError(null);
    const referenceTrimmed = referencePlayer.trim();
    if (!referenceTrimmed) { setSearching(false); setSearchError('Please provide a reference player name or id.'); return; }
    const payload: Record<string, unknown> = { limit };
    if (selectedReferencePlayerId !== null) payload.player_id = selectedReferencePlayerId; else payload.player_name = referenceTrimmed;
    if (season.trim()) payload.season = season.trim();
    const minAgeNumber = toOptionalNumber(minAge); const maxAgeNumber = toOptionalNumber(maxAge);
    if (minAgeNumber !== null) payload.min_age = minAgeNumber;
    if (maxAgeNumber !== null) payload.max_age = maxAgeNumber;
    if (position.trim()) payload.position = position.trim();
    if (activeMode !== 'any') payload.is_active = activeMode === 'true';
    try {
      const response = await fetch('/api/search/similar-players', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      if (!response.ok) throw new Error((await response.json().catch(() => null) as { detail?: string } | null)?.detail || 'Hybrid search request failed.');
      setSearchResults(await response.json() as SimilarPlayerResult[]);
    } catch (err) { setSearchResults([]); setSearchError(err instanceof Error ? err.message : 'Unknown search error.'); }
    finally { setSearching(false); }
  };
  const handleAsk = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); const question = ragQuestion.trim(); if (!question) return;
    setAsking(true); setRagError(null); setRagResponse(null);
    try {
      const response = await fetch('/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question, season: ragSeason.trim() || null, limit: 6 }) });
      if (!response.ok) throw new Error((await response.json().catch(() => null) as { detail?: string } | null)?.detail || 'Unable to generate an answer.');
      setRagResponse(await response.json() as AskResponse);
    } catch (err) { setRagError(err instanceof Error ? err.message : 'Unknown RAG error.'); }
    finally { setAsking(false); }
  };

  function playerButton(player: PlayerDirectoryRow | SimilarPlayerResult) { return <button type="button" className="player-link" onClick={() => openPlayer(player.player_id)}>{'nba_player_id' in player && <img className="player-thumb" src={playerImage(player.nba_player_id)} alt="" onError={(event) => { event.currentTarget.style.display = 'none'; }} />}{player.full_name}<span>↗</span></button>; }
  const historyStrip = <section className="history-strip"><div><p className="section-kicker">Recently viewed</p><h2>Trace your scouting trail</h2></div><div className="history-items">{historyPlayers.length ? historyPlayers.map((player) => <button type="button" key={player.player_id} onClick={() => openPlayer(player.player_id)}>{player.full_name}</button>) : <span className="history-empty">Players you open will appear here.</span>}</div></section>;
  const compactTable = (rows: PlayerDirectoryRow[]) => <div className="table-wrap"><table><thead><tr><th><button type="button" className="sort-heading" onClick={() => sortBy('name')}>Name{sortIndicator('name')}</button></th><th><button type="button" className="sort-heading" onClick={() => sortBy('club')}>Club{sortIndicator('club')}</button></th>{[['points', 'PTS'], ['rebounds', 'REB'], ['assists', 'AST'], ['games_played', 'GP'], ['minutes', 'MIN'], ['steals', 'STL'], ['blocks', 'BLK'], ['turnovers', 'TOV'], ['field_goal_pct', 'FG%'], ['three_point_pct', '3P%'], ['free_throw_pct', 'FT%']].map(([key, label]) => <th key={key}><button type="button" className="sort-heading" onClick={() => sortBy(key as SortKey)}>{label}{sortIndicator(key as SortKey)}</button></th>)}<th>Status</th><th aria-label="Favorite" /></tr></thead><tbody>{rows.map((player, index) => <tr key={player.player_id} style={{ animationDelay: `${index * 25}ms` }}><td>{playerButton(player)}</td><td><span className="club-cell">{teamLogo(player.club_team_id) && <img src={teamLogo(player.club_team_id) ?? ''} alt="" />}{player.club_full_name ? `${player.club_full_name} (${player.club})` : '-'}</span></td><td>{player.points?.toFixed(1) ?? '-'}</td><td>{player.rebounds?.toFixed(1) ?? '-'}</td><td>{player.assists?.toFixed(1) ?? '-'}</td><td>{player.games_played ?? '-'}</td><td>{player.minutes?.toFixed(1) ?? '-'}</td><td>{player.steals?.toFixed(1) ?? '-'}</td><td>{player.blocks?.toFixed(1) ?? '-'}</td><td>{player.turnovers?.toFixed(1) ?? '-'}</td><td>{player.field_goal_pct == null ? '-' : `${player.field_goal_pct.toFixed(1)}%`}</td><td>{player.three_point_pct == null ? '-' : `${player.three_point_pct.toFixed(1)}%`}</td><td>{player.free_throw_pct == null ? '-' : `${player.free_throw_pct.toFixed(1)}%`}</td><td><span className={`pill ${player.is_active ? 'active' : 'inactive'}`}>{player.is_active ? 'Active' : 'Inactive'}</span></td><td><button type="button" className={`favorite-button ${favoriteIds.includes(player.player_id) ? 'is-favorite' : ''}`} onClick={() => toggleFavorite(player.player_id)} aria-label={`${favoriteIds.includes(player.player_id) ? 'Remove' : 'Add'} ${player.full_name} ${favoriteIds.includes(player.player_id) ? 'from' : 'to'} shortlist`}>{favoriteIds.includes(player.player_id) ? '❤' : '♡'}</button></td></tr>)}</tbody></table></div>;
  const statFilterPanel = <div className="directory-stat-filters"><button type="button" className="filter-toggle" onClick={() => setShowStatFilters((visible) => !visible)}><span>Filter by minimum stats</span><strong>{showStatFilters ? '−' : '+'}</strong></button>{showStatFilters && <div className="stat-filter-grid">{([['points', 'Points per game', 40, .5], ['rebounds', 'Rebounds per game', 20, .5], ['assists', 'Assists per game', 15, .5], ['minutes', 'Minutes per game', 40, .5], ['steals', 'Steals per game', 5, .1], ['blocks', 'Blocks per game', 5, .1], ['turnovers', 'Turnovers per game', 10, .1], ['field_goal_pct', 'Field goal %', 100, 1], ['three_point_pct', 'Three-point %', 100, 1], ['free_throw_pct', 'Free throw %', 100, 1]] as [keyof DirectoryStatFilters, string, number, number][]).map(([key, label, max, step]) => <label className="range-filter" key={key}><span><b>{label}</b><output>{statFilters[key].toFixed(step < 1 ? 1 : 0)}{key.includes('pct') ? '%' : ''}</output></span><input type="range" min="0" max={max} step={step} value={statFilters[key]} onChange={(event) => updateStatFilter(key, Number(event.target.value))} /></label>)}<button type="button" className="reset-filter" onClick={resetStatFilters}>Reset stat filters</button></div>}</div>;
  const advancedStatsPanel = <div className="advanced-stats-panel"><button type="button" className="advanced-stats-toggle" onClick={() => showAdvancedStats ? setShowAdvancedStats(false) : void loadAdvancedStats()}>{showAdvancedStats ? 'Hide advanced stats' : 'View advanced stats'}</button></div>;

  const directoryView = <>
    <section className="panel panel-directory"><div className="panel-header"><div><p className="section-kicker">Browse the pool</p><h2>Player Directory</h2></div><p className="count-label">{filteredPlayers.length.toLocaleString()} players with stats</p></div><div className="toolbar directory-filters"><input value={directoryQuery} onChange={(event) => setDirectoryQuery(event.target.value)} placeholder="Search by player name" className="control-input" /><select value={clubFilter} onChange={(event) => setClubFilter(event.target.value)} className="control-input"><option value="">All clubs</option>{clubOptions.map((club) => <option key={club} value={club}>{club}</option>)}</select></div>{statFilterPanel}{loadingPlayers && <p className="status">Loading players...</p>}{playersError && <p className="status error">{playersError}</p>}{!loadingPlayers && !playersError && <><div className="table-label">Click a category to sort ascending or descending <span>♥ saves to shortlist</span></div>{compactTable(pagedPlayers)}<div className="pagination"><button type="button" className="nav-button" disabled={currentPage <= 1} onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}>Prev</button><span>Page {Math.min(currentPage, pageCount)} / {pageCount}</span><button type="button" className="nav-button" disabled={currentPage >= pageCount} onClick={() => setCurrentPage((page) => Math.min(pageCount, page + 1))}>Next</button></div></>}{advancedStatsPanel}</section>
    <section className="panel panel-search"><div className="panel-header"><div><p className="section-kicker">Find a comparable</p><h2>Hybrid Search</h2></div><p className="count-label">Vector + SQL</p></div><form className="search-form" onSubmit={handleHybridSearch}><label>Reference player<input className="control-input" value={referencePlayer} onFocus={() => setShowReferenceOptions(true)} onBlur={() => setTimeout(() => setShowReferenceOptions(false), 140)} onChange={(event) => { setReferencePlayer(event.target.value); setSelectedReferencePlayerId(null); setShowReferenceOptions(true); }} placeholder="Type a player name" />{showReferenceOptions && referenceOptions.length > 0 && <div className="autocomplete-list" role="listbox">{referenceOptions.map((option) => <button type="button" key={option.player_id} className="autocomplete-item" onMouseDown={() => { setReferencePlayer(option.full_name); setSelectedReferencePlayerId(option.player_id); setShowReferenceOptions(false); }}>{option.full_name}</button>)}</div>}</label><div className="grid-2"><label>Season<input className="control-input" value={season} onChange={(event) => setSeason(event.target.value)} placeholder="Any season (e.g. 2024-25)" /></label><label>Results count<input className="control-input" type="number" min={1} max={50} value={limit} onChange={(event) => setLimit(Math.max(1, Math.min(50, Number(event.target.value) || 1)))} /><small className="help-text">Top-K nearest players.</small></label></div><div className="grid-3"><label>Min age<input className="control-input" type="number" min={0} value={minAge} onChange={(event) => setMinAge(event.target.value)} placeholder="Any" /></label><label>Max age<input className="control-input" type="number" min={0} value={maxAge} onChange={(event) => setMaxAge(event.target.value)} placeholder="Any" /></label><label>Position<select className="control-input" value={position} onChange={(event) => setPosition(event.target.value)}><option value="">Any</option>{positionOptions.map((option) => <option key={option} value={option}>{option}</option>)}</select></label></div><label>Active status<select className="control-input" value={activeMode} onChange={(event) => setActiveMode(event.target.value as ActiveFilterMode)}><option value="any">Any</option><option value="true">Active only</option><option value="false">Inactive only</option></select></label><button type="submit" className="submit-button" disabled={searching}>{searching ? 'Searching...' : 'Run hybrid search'}</button></form>{searchError && <p className="status error">{searchError}</p>}{!searchError && searchResults.length > 0 && <div className="results-list">{searchResults.map((result, index) => <article className="result-card" key={`${result.player_id}-${result.season}-${index}`}><div className="result-head"><h3>{playerButton(result)}</h3><span className="score">{(result.similarity * 100).toFixed(1)}%</span></div><div className="meta-row"><span>Season: {result.season}</span><span>Age: {result.age ?? 'N/A'}</span><span>Position: {result.position ?? 'N/A'}</span></div></article>)}</div>}{!searchError && !searching && searchResults.length === 0 && <div className="empty-state"><span className="empty-mark">+</span><p>No similarity results yet.</p><small>Choose a reference player and tune the filters.</small></div>}</section>
  </>;

  const ragPanel = <section className="panel rag-panel"><div className="panel-header"><div><p className="section-kicker">Evidence layer</p><h2>Ask the scouting assistant</h2><p>Natural-language retrieval with database-grounded answers</p></div>{ragResponse && <span className="provider-badge">{ragResponse.provider} · {ragResponse.model}</span>}</div><form className="rag-form" onSubmit={handleAsk}><textarea className="control-input rag-question" value={ragQuestion} onChange={(event) => setRagQuestion(event.target.value)} rows={3} placeholder="Ask about player styles, strengths, or comparisons..." /><div className="rag-actions"><input className="control-input" value={ragSeason} onChange={(event) => setRagSeason(event.target.value)} placeholder="Optional season (2024-25)" /><button type="submit" className="submit-button" disabled={asking || !ragQuestion.trim()}>{asking ? 'Retrieving evidence...' : 'Ask with RAG'}</button></div></form>{ragError && <p className="status error">{ragError}</p>}{ragResponse && <div className="rag-output"><p className="rag-answer">{ragResponse.answer}</p><details className="evidence-box"><summary>{ragResponse.sources.length} retrieved evidence sources</summary><div className="evidence-grid">{ragResponse.sources.map((source) => <article key={`${source.player_id}-${source.season}`} className="evidence-card"><div className="result-head"><strong>{source.full_name}</strong><span className="score">{(source.similarity * 100).toFixed(1)}%</span></div><small>{source.season}</small><p>{source.source_text}</p></article>)}</div></details></div>}</section>;

  const groupedPlayers = activeGroup === 'All saved' ? favoritePlayers : favoritePlayers.filter((player) => groups[activeGroup]?.includes(player.player_id));
  const shortlistView = <section className="panel shortlist-page"><div className="panel-header"><div><p className="section-kicker">Saved for later</p><h2>Your Shortlist</h2></div><p className="count-label">{groupedPlayers.length} saved players</p></div><div className="group-toolbar"><div className="group-tabs"><button type="button" className={activeGroup === 'All saved' ? 'group-tab active' : 'group-tab'} onClick={() => setActiveGroup('All saved')}>All saved</button>{groupNames.map((name) => <button type="button" className={activeGroup === name ? 'group-tab active' : 'group-tab'} key={name} onClick={() => setActiveGroup(name)}>{name}</button>)}</div><form className="group-create" onSubmit={createGroup}><input className="control-input" value={newGroupName} onChange={(event) => setNewGroupName(event.target.value)} placeholder="New scouting group" /><button className="nav-button" type="submit">Create group</button></form></div>{groupedPlayers.length ? <div className="shortlist-table"><div className="group-assignment-label">Assign saved players to a scouting role</div>{groupedPlayers.map((player) => <div className="shortlist-row" key={player.player_id}>{playerButton(player)}<span className="club-cell">{player.club_full_name ?? player.club ?? '-'}</span><select className="control-input group-select" value={groupNames.find((name) => groups[name]?.includes(player.player_id)) ?? ''} onChange={(event) => assignToGroup(player.player_id, event.target.value)}><option value="">No group</option>{groupNames.map((name) => <option value={name} key={name}>{name}</option>)}</select><button type="button" className="favorite-button is-favorite" onClick={() => toggleFavorite(player.player_id)} aria-label={`Remove ${player.full_name} from shortlist`}>♥</button></div>)}</div> : <div className="empty-state"><span className="empty-mark">♥</span><p>{activeGroup === 'All saved' ? 'Your shortlist is empty.' : 'This group has no players yet.'}</p><small>Save players and organize them into roles such as Sixth Man or Starting PG replacement.</small></div>}</section>;
  const detailView = detail ? <section className="player-detail"><div className="detail-topbar"><button type="button" className="back-button" onClick={goBack}>← Back to directory</button><button type="button" className={`favorite-button detail-favorite ${favoriteIds.includes(detail.player.id) ? 'is-favorite' : ''}`} onClick={() => toggleFavorite(detail.player.id)}>{favoriteIds.includes(detail.player.id) ? '★ On shortlist' : '☆ Add to shortlist'}</button></div><div className="detail-hero"><div><p className="section-kicker">Player profile / {detail.stats[0]?.season ?? 'Career'}</p><h2>{detail.player.full_name}</h2><p className="detail-subtitle">{detail.player.is_active ? 'Active roster player' : 'Historical player'} · NBA ID {detail.player.nba_player_id}</p></div><div className="detail-mark">{detail.player.first_name.slice(0, 1)}{detail.player.last_name.slice(0, 1)}</div></div><div className="stat-ribbon">{detail.stats[0] ? <><div><strong>{detail.stats[0].points.toFixed(1)}</strong><span>PTS</span></div><div><strong>{detail.stats[0].rebounds.toFixed(1)}</strong><span>REB</span></div><div><strong>{detail.stats[0].assists.toFixed(1)}</strong><span>AST</span></div><div><strong>{detail.stats[0].games_played}</strong><span>GP</span></div></> : <p>No season statistics available.</p>}</div><div className="detail-grid"><section className="panel"><div className="panel-header"><div><p className="section-kicker">Season by season</p><h2>Performance log</h2></div></div><div className="stats-list">{detail.stats.map((stat) => <div className="season-row" key={stat.season}><strong>{stat.season}</strong><span>{stat.points.toFixed(1)} PTS</span><span>{stat.rebounds.toFixed(1)} REB</span><span>{stat.assists.toFixed(1)} AST</span><span>{stat.minutes.toFixed(1)} MIN</span><span>{stat.field_goal_pct == null ? '-' : `${stat.field_goal_pct.toFixed(1)} FG%`}</span></div>)}</div></section><section className="panel"><div className="panel-header"><div><p className="section-kicker">Next reads</p><h2>Similar players</h2></div></div><div className="similar-list">{detail.similar.length ? detail.similar.map((result) => <div className="similar-row" key={`${result.player_id}-${result.season}`}>{playerButton(result)}<span className="score">{(result.similarity * 100).toFixed(1)}%</span></div>) : <p className="status">No similar profiles available.</p>}</div></section></div></section> : <section className="panel detail-loading"><p className="status">{detailError || (detailLoading ? 'Loading player profile...' : 'Choose a player to view details.')}</p></section>;

  return <div className="app-shell"><div className="background-grid" aria-hidden="true" /><header className="hero"><div className="hero-topline"><p className="eyebrow">Basketball intelligence / 01</p><span className="live-dot">Data connected</span></div><h1>Scouting<br /><span>Console</span></h1><p className="hero-copy">Find the right player, understand the evidence, and move from a question to a defensible shortlist.</p><div className="hero-meta"><span>Directory <strong>{players.length || '—'}</strong></span><span>Shortlist <strong>{favoriteIds.length}</strong></span><span>Evidence <strong>Grounded</strong></span></div></header><nav className="main-nav"><button type="button" className={view === 'directory' ? 'nav-tab active' : 'nav-tab'} onClick={() => { setView('directory'); window.history.pushState({ view: 'directory' }, '', '#directory'); }}>Directory</button><button type="button" className={view === 'shortlist' ? 'nav-tab active' : 'nav-tab'} onClick={openShortlist}>Shortlist <span>{favoriteIds.length}</span></button></nav>{view === 'player' ? detailView : <>{historyStrip}{view === 'shortlist' ? shortlistView : <><main className="layout-grid">{directoryView}</main>{ragPanel}</>}</>}</div>;
}

export default App;
