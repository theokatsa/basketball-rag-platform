import { useMemo, useState } from 'react';
import type { PlayerDetailData } from '../types';
import { fractionPct, radarMetrics, rankLabel, topFromStrength, topLabel } from '../utils';
import { Avatar } from './Avatar';
import { GameLogs } from './GameLogs';
import { BackIcon, CompareIcon, HeartIcon } from './Icons';
import { PlayerLink } from './PlayerLink';
import { averageStrength, RadarChart, toneFor } from './RadarChart';
import { ShotChart } from './ShotChart';

type Props = {
  detail: PlayerDetailData | null;
  loading: boolean;
  error: string | null;
  favorite: boolean;
  comparing: boolean;
  compareFull: boolean;
  nbaIdOf: (playerId: number) => number | undefined;
  onBack: () => void;
  onToggleFavorite: (playerId: number) => void;
  onToggleCompare: (playerId: number) => void;
  onOpen: (playerId: number) => void;
  onReport: (playerId: number) => void;
};

const METRIC_NAMES: Record<string, string> = { PTS: 'Points', REB: 'Rebounds', AST: 'Assists', STL: 'Steals', BLK: 'Blocks', 'FG%': 'Field goal %' };
const formatHeight = (h: string) => (/^\d+-\d+$/.test(h) ? `${h.replace('-', "'")}"` : h);

export function PlayerDetail({ detail, loading, error, favorite, comparing, compareFull, nbaIdOf, onBack, onToggleFavorite, onToggleCompare, onOpen, onReport }: Props) {
  const [shotSeason, setShotSeason] = useState('all');
  const [scope, setScope] = useState<'position' | 'all'>('position');
  const allShots = detail?.shots;
  const shotSeasons = useMemo(() => [...new Set((allShots ?? []).map((s) => s.season))].sort().reverse(), [allShots]);
  const shots = useMemo(() => (allShots ?? []).filter((s) => shotSeason === 'all' || s.season === shotSeason), [allShots, shotSeason]);

  if (!detail) {
    return (
      <section className="player-detail">
        <div className="detail-topbar"><button type="button" className="back-button" onClick={onBack}><BackIcon />Back</button></div>
        {loading && !error
          ? <div className="skeleton-block" aria-busy="true" aria-label="Loading player"><span className="skeleton" style={{ height: '13rem' }} /><span className="skeleton" style={{ height: '6rem' }} /><span className="skeleton" style={{ height: '20rem' }} /></div>
          : <div className="panel"><p className="status error" role="alert">{error ?? 'Player not found.'}</p></div>}
      </section>
    );
  }

  const { player, profile, stats, logs, similar } = detail;
  const latest = stats[0];
  const position = profile.position;
  const activeScope = position ? scope : 'all';
  const metrics = latest ? radarMetrics(latest, activeScope) : [];
  const avg = averageStrength(metrics);
  const facts = [position, profile.age != null && `${profile.age} years old`, profile.height && formatHeight(profile.height), profile.weight && `${profile.weight} lb`, player.is_active ? 'Active' : 'Inactive'].filter(Boolean);
  const tiles: [string, string, number | null][] = latest
    ? [
        ['Points', latest.points.toFixed(1), latest.points_rank], ['Rebounds', latest.rebounds.toFixed(1), latest.rebounds_rank], ['Assists', latest.assists.toFixed(1), latest.assists_rank],
        ['Steals', latest.steals.toFixed(1), latest.steals_rank], ['Blocks', latest.blocks.toFixed(1), latest.blocks_rank], ['Turnovers', latest.turnovers.toFixed(1), null],
        ['Minutes', latest.minutes.toFixed(1), null], ['FG%', fractionPct(latest.field_goal_pct), latest.field_goal_rank], ['3P%', fractionPct(latest.three_point_pct), latest.three_point_rank], ['FT%', fractionPct(latest.free_throw_pct), latest.free_throw_rank],
      ]
    : [];

  return (
    <section className="player-detail">
      <div className="detail-topbar">
        <button type="button" className="back-button" onClick={onBack}><BackIcon />Back</button>
        <div className="detail-actions">
          <button type="button" className="ghost-button" onClick={() => onReport(player.id)}>Scouting report</button>
          <button type="button" className="ghost-button" aria-pressed={comparing} disabled={!comparing && compareFull} title={!comparing && compareFull ? 'Comparison is full (3 players)' : undefined} onClick={() => onToggleCompare(player.id)}><CompareIcon />{comparing ? 'In comparison' : 'Compare'}</button>
          <button type="button" className="ghost-button" aria-pressed={favorite} onClick={() => onToggleFavorite(player.id)}><HeartIcon filled={favorite} />{favorite ? 'Shortlisted' : 'Shortlist'}</button>
        </div>
      </div>

      <header className="detail-hero">
        <div className="detail-hero-main">
          <Avatar name={player.full_name} nbaPlayerId={player.nba_player_id} className="detail-mark" />
          <div className="detail-title">
            <h2>{player.full_name}</h2>
            <ul className="fact-list">{facts.map((fact) => <li key={String(fact)}>{fact}</li>)}</ul>
          </div>
          {latest && <p className="hero-season">{latest.season}<span>{latest.games_played} games</span></p>}
        </div>
        {latest
          ? <dl className="stat-tiles">{tiles.map(([label, value, rank]) => <div key={label} className={rank != null && rank <= 25 ? 'elite' : ''}><dt>{label}</dt><dd>{value}</dd><dd className="tile-note">{rank != null ? `${rankLabel(rank)} in league` : 'per game'}</dd></div>)}</dl>
          : <p className="status">No season statistics available.</p>}
      </header>

      <div className="detail-grid">
        {latest && (
          <section className="panel">
            <div className="panel-header">
              <div><h2>Strengths</h2><p>{activeScope === 'position' ? `Compared with other ${position?.toLowerCase()}s` : 'Compared with every player'}</p></div>
              {position && <div className="segmented" role="group" aria-label="Comparison group">{([['position', `${position}s`], ['all', 'League']] as ['position' | 'all', string][]).map(([key, label]) => <button key={key} type="button" aria-pressed={scope === key} className={scope === key ? 'segment active' : 'segment'} onClick={() => setScope(key)}>{label}</button>)}</div>}
            </div>
            <div className="profile-body">
              <RadarChart series={[{ name: player.full_name, color: '#ff6a13', metrics }]} label={`Percentile radar chart for ${player.full_name}`} />
              <div className="strength-bars">
                {metrics.map((m) => {
                  const strength = m.percentile == null ? 0 : 1 - m.percentile;
                  return (
                    <div key={m.label} className="strength-row">
                      <span>{METRIC_NAMES[m.label]}</span><b>{topLabel(m.percentile)}</b>
                      <i><em style={{ width: `${strength * 100}%`, background: toneFor(strength) }} /></i>
                    </div>
                  );
                })}
                <p className="strength-total">Average across all six <b>{topFromStrength(avg)}</b></p>
              </div>
            </div>
          </section>
        )}

        <section className="panel">
          <div className="panel-header"><div><h2>Similar players</h2><p>Closest statistical profiles</p></div></div>
          <div className="similar-list">
            {similar.length ? similar.map((result) => <div className="similar-row" key={`${result.player_id}-${result.season}`}><PlayerLink playerId={result.player_id} name={result.full_name} nbaPlayerId={nbaIdOf(result.player_id)} onOpen={onOpen} /><span title={result.shared_traits.join(', ')} className="score">{Math.round(result.similarity * 100)}%</span></div>) : <p className="status">No similar profiles available.</p>}
          </div>
        </section>

        <section className="panel wide">
          <div className="panel-header">
            <div><h2>Shot chart</h2></div>
            {shotSeasons.length > 1 && <select className="control-input compact-select" value={shotSeason} onChange={(e) => setShotSeason(e.target.value)} aria-label="Shot chart season"><option value="all">All seasons</option>{shotSeasons.map((s) => <option key={s} value={s}>{s}</option>)}</select>}
          </div>
          {allShots ? <ShotChart shots={shots} /> : <span className="skeleton" style={{ height: '30rem' }} />}
        </section>

        {logs ? <GameLogs logs={logs} /> : <section className="panel wide"><span className="skeleton" style={{ height: '20rem' }} /></section>}

        {stats.length > 1 && (
          <section className="panel wide">
            <div className="panel-header"><div><h2>Season by season</h2></div></div>
            <div className="detail-records-scroll">
              <table className="detail-records-table">
                <thead><tr>{['Season', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'MIN', 'FG%', '3P%', 'FT%'].map((h) => <th scope="col" key={h}>{h}</th>)}</tr></thead>
                <tbody>{stats.map((s) => <tr key={s.season}><th scope="row">{s.season}</th>{[s.points, s.rebounds, s.assists, s.steals, s.blocks, s.turnovers, s.minutes].map((v, i) => <td key={i}>{v.toFixed(1)}</td>)}<td>{fractionPct(s.field_goal_pct)}</td><td>{fractionPct(s.three_point_pct)}</td><td>{fractionPct(s.free_throw_pct)}</td></tr>)}</tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </section>
  );
}
