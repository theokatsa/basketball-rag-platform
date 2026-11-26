import { useMemo } from 'react';
import { useApp } from '../AppContext';
import { Avatar } from '../components/Avatar';
import { LoadError, Loading, PageHead, PlayerCell, Segmented, TeamLogo } from '../components/Common';
import { Dropdown, TeamSelect } from '../components/Dropdown';
import { Pagination, usePaged } from '../components/Pagination';
import { playsPosition, POSITIONS } from '../stats';
import type { FormRow, FormStat } from '../types';
import { useApi } from '../useApi';
import { usePersisted } from '../usePersisted';

type Def = { key: string; label: string; short: string; suffix?: string; lower?: boolean; signed?: boolean };
const DEFS: Def[] = [
  { key: 'game_score', label: 'Game Score (overall)', short: 'GmSc' }, { key: 'points', label: 'Points', short: 'PTS' }, { key: 'reb', label: 'Rebounds', short: 'REB' }, { key: 'ast', label: 'Assists', short: 'AST' },
  { key: 'tpm', label: 'Threes made', short: '3PM' }, { key: 'stl', label: 'Steals', short: 'STL' }, { key: 'blk', label: 'Blocks', short: 'BLK' }, { key: 'tov', label: 'Turnovers', short: 'TOV', lower: true },
  { key: 'ts', label: 'True shooting', short: 'TS%', suffix: '%' }, { key: 'fg', label: 'Field goal %', short: 'FG%', suffix: '%' }, { key: 'three', label: 'Three-point %', short: '3P%', suffix: '%' }, { key: 'plus_minus', label: 'Plus/minus', short: '+/−', signed: true }, { key: 'minutes', label: 'Minutes', short: 'MIN' },
];
const LINE = ['points', 'reb', 'ast', 'ts', 'minutes', 'game_score'];
const def = (key: string) => DEFS.find((d) => d.key === key) ?? DEFS[0];
const text = (d: Def, v: number, plus = d.signed) => `${plus && v > 0 ? '+' : ''}${v.toFixed(1)}${d.suffix ?? ''}`;
/** 0 ordinary, 3 very unusual for this player. */
const level = (s: number) => Math.min(3, Math.floor(Math.abs(s)));
const WORDS = ['Within normal range', 'A little unusual', 'Unusual', 'Very unusual'];

function Spark({ stat, d, big = false }: { stat: FormStat; d: Def; big?: boolean }) {
  const values = stat.games.filter((v): v is number => v != null);
  const hi = Math.max(1, stat.before, ...values), lo = Math.min(0, stat.before, ...values);
  const y = (v: number) => ((v - lo) / (hi - lo)) * 100;
  return (
    <span className={`form-spark ${big ? 'big' : ''}`} role="img" aria-label={`Last games: ${values.join(', ')}. Average before: ${text(d, stat.before)}`}>
      <u style={{ bottom: `${y(stat.before)}%` }} />
      {stat.games.map((v, i) => <i key={i} title={v == null ? 'No attempts' : text(d, v)}>{v != null && <em className={(v >= stat.before) !== Boolean(d.lower) ? 'good' : ''} style={{ bottom: `${y(Math.min(0, v))}%`, height: `${Math.max(3, Math.abs(y(v) - y(0)))}%` }} />}</i>)}
    </span>
  );
}

export function Form() {
  const { byId, loading, error, open } = useApp();
  const [recent, setRecent] = usePersisted('form-window', '10');
  const { data, error: formError } = useApi<FormRow[]>(`/form?games=${recent}`);
  const [key, setKey] = usePersisted('form-key', 'game_score');
  const [rank, setRank] = usePersisted<'surprise' | 'change'>('form-rank', 'surprise');
  const [club, setClub] = usePersisted('form-club', '');
  const [position, setPosition] = usePersisted('form-pos', '');
  const [minutes, setMinutes] = usePersisted('form-minutes', 18);
  const d = def(key);
  const rows = useMemo(() => (data ?? []).flatMap((f) => {
    const p = byId.get(f.player_id), s = f.stats[key], mins = f.stats.minutes;
    if (!p || !s || !mins || Math.max(mins.now, mins.before) < minutes || (club && p.club_full_name !== club) || !playsPosition(p, position)) return [];
    const change = s.now - s.before;
    return [{ f, p, s, change, score: (d.lower ? -1 : 1) * (rank === 'surprise' ? s.surprise : change) }];
  }).sort((a, b) => b.score - a.score), [data, byId, key, d, rank, club, position, minutes]);
  const hot = useMemo(() => rows.filter((r) => r.score > 0), [rows]);
  const cold = useMemo(() => rows.filter((r) => r.score < 0).reverse(), [rows]);
  const reset = [key, rank, club, position, minutes, recent].join('|');
  const hotPage = usePaged(hot, 8, reset), coldPage = usePaged(cold, 8, reset);
  if (error || formError) return <LoadError message={(error ?? formError)!} />;
  const hero = (r: (typeof rows)[number] | undefined, warm: boolean) => r && (
    <button type="button" className={`form-hero ${warm ? 'hot' : 'cold'}`} onClick={() => open(r.p.player_id)}>
      <span className="form-hero-logo"><TeamLogo teamId={r.p.club_team_id} size={190} /></span>
      <Avatar key={r.p.nba_player_id} name={r.p.full_name} nbaPlayerId={r.p.nba_player_id} className="form-hero-photo" />
      <span className="form-hero-text"><small className="form-hero-kicker">{rank === 'surprise' ? (warm ? 'Most unusual rise' : 'Most unusual drop') : (warm ? 'Biggest rise' : 'Biggest drop')}</small><b>{r.p.full_name}</b><strong>{text(d, r.s.now)}<em>{text(d, r.change, true)}</em></strong><small>{d.label.replace(' (overall)', '')} over the last {recent}, was {text(d, r.s.before)}</small></span>
      <span className="form-hero-spark"><Spark stat={r.s} d={d} big /><small>Last {recent} games, oldest first</small></span>
    </button>
  );
  const list = (warm: boolean, paged: typeof hotPage) => (
    <section className={`panel form-panel ${warm ? 'hot' : 'cold'}`}>
      <div className="panel-header"><h2>{warm ? 'Heating up' : 'Cooling off'}</h2><span className="count-label">{(warm ? hot : cold).length} players</span></div>
      <ol className="form-cards">
        {paged.items.map(({ f, p, s, change }) => (
          <li key={f.player_id}>
            <div className="form-main">
              <PlayerCell player={p} />
              <Spark stat={s} d={d} />
              <span className="form-now"><b>{text(d, s.now)}</b><small>was {text(d, s.before)}</small></span>
              <span className="form-delta"><b>{text(d, change, true)}</b><span className="heat-dots" role="img" aria-label={WORDS[level(s.surprise)]} title={WORDS[level(s.surprise)]}>{[0, 1, 2].map((n) => <i key={n} className={n < level(s.surprise) ? 'on' : ''} />)}</span></span>
            </div>
            <dl className="form-line">{LINE.filter((k) => k !== key).slice(0, 5).map((k) => { const x = f.stats[k], dd = def(k); return x && <div key={k}><dt>{dd.short}</dt><dd>{text(dd, x.now)}<small className={x.now - x.before > 0 ? 'up' : 'down'}>{text(dd, x.now - x.before, true).replace('%', '')}</small></dd></div>; })}</dl>
          </li>
        ))}
        {!paged.items.length && <li className="status">Nobody matches.</li>}
      </ol>
      <Pagination page={paged.page} pageCount={paged.pageCount} onPage={paged.onPage} label={`${warm ? 'Heating up' : 'Cooling off'} pages`} />
    </section>
  );
  return (
    <>
      <PageHead title="Hot and cold" intro="Each player's last games of 2024-25 against the rest of the same season." />
      <div className="filter-bar">
        <Dropdown label="Statistic" value={key} options={DEFS.map((x) => ({ value: x.key, label: x.label, note: x.short }))} onChange={setKey} />
        <TeamSelect value={club} onChange={setClub} />
        <Segmented label="Position" value={position} options={[['', 'All'], ...POSITIONS.map((p) => [p, `${p}s`] as [string, string])]} onChange={setPosition} />
        <Segmented label="Recent games" value={recent} options={[['5', 'Last 5'], ['10', 'Last 10'], ['15', 'Last 15'], ['20', 'Last 20']]} onChange={setRecent} />
        <Segmented label="Rank by" value={rank} options={[['surprise', 'Most unusual'], ['change', 'Biggest change']]} onChange={setRank} />
        <label className="inline-range">At least {minutes} min a game<input type="range" min={5} max={36} value={minutes} onChange={(e) => setMinutes(Number(e.target.value))} /></label>
      </div>
      {!data || loading ? <Loading height="34rem" /> : (
        <>
          <div className="form-heroes">{hero(hot[0], true)}{hero(cold[0], false)}</div>
          <div className="form-key" aria-label="How to read the lists">
            <span><i className="key-bars" aria-hidden="true"><em /><em /><em /></i>One bar per game, oldest first</span>
            <span><i className="key-line" aria-hidden="true" />The earlier average</span>
            <span><span className="heat-dots" aria-hidden="true"><i className="on" /><i className="on" /><i /></span>How unusual the change is for that player, against his normal game-to-game swings</span>
          </div>
          <div className="two-col">{list(true, hotPage)}{list(false, coldPage)}</div>
        </>
      )}
    </>
  );
}
