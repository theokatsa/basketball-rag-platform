import { useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useApp } from '../AppContext';
import { Avatar } from '../components/Avatar';
import { LoadError, Loading, TeamLogo } from '../components/Common';
import { ChevronIcon } from '../components/Icons';
import { MostViewed } from '../components/MostViewed';
import { Suggested } from '../components/Suggested';
import { formatStat, qualifies, statByKey } from '../stats';
import type { BestGame, FormRow, FormStat, PlayerDirectoryRow } from '../types';
import { useApi } from '../useApi';
import { teamVars } from '../teamColors';
import { formatDate } from '../utils';
import { rememberFor } from '../usePersisted';

const BOARDS = ['points', 'rebounds', 'assists', 'steals', 'blocks', 'threes'];
const SPOT_STATS = ['points', 'rebounds', 'assists', 'ts'];
// Counted from the database on 2026-11-26 (shot_charts, player_matchups, team_box_scores); one season.
const PROOF: [string, string][] = [['217,398', 'shots mapped'], ['65,946', 'defender matchups'], ['1,230', 'games'], ['569', 'players']];

type Ranking = { items: { player_id: number; viewers: number }[] };

/** The five players opened by the most people in the last day; the week when the day is quiet. */
function MostSearched() {
  const { byId, players, totals, open, go } = useApp();
  const today = useApi<Ranking>('/audience/players?view=most&days=1&limit=5');
  const week = useApi<Ranking>(today.data && today.data.items.length < 5 ? '/audience/players?view=most&days=7&limit=5' : null);
  const ranking = today.data && today.data.items.length >= 5 ? today.data : week.data;
  const league = useMemo(() => players.filter((p) => (p.games_played ?? 0) >= 40 && (p.minutes ?? 0) >= 15), [players]);
  if (today.error) return null;
  if (!ranking) return <Loading height="16rem" />;
  const list = ranking.items.flatMap((item) => { const p = byId.get(item.player_id); return p ? [{ p, viewers: item.viewers }] : []; });
  if (!list.length) return null;
  const [first, ...rest] = list;
  const percentile = (p: PlayerDirectoryRow, key: string) => {
    const stat = statByKey(key), mine = stat.get(p, totals[p.player_id]);
    const values = league.map((o) => (qualifies(stat, totals[o.player_id]) ? stat.get(o, totals[o.player_id]) : null)).filter((v): v is number => v != null);
    return mine == null || !values.length ? null : { mine, pct: Math.round((values.filter((v) => v < mine).length / values.length) * 100) };
  };
  const period = ranking === today.data ? 'today' : 'this week';
  return (
    <Band tone="gold" title={`Most searched ${period}`} note="The players opened by the most different people" action={<button type="button" className="more-link" onClick={() => go('players')}>Browse all players<ChevronIcon /></button>}>
    <div className="searched">
      <button type="button" className="searched-first" style={teamVars(first.p.club_team_id)} onClick={() => open(first.p.player_id)}>
        <span className="searched-logo"><TeamLogo teamId={first.p.club_team_id} size={200} /></span>
        <span className="searched-number" aria-hidden="true">#1</span>
        <Avatar key={first.p.nba_player_id} name={first.p.full_name} nbaPlayerId={first.p.nba_player_id} className="searched-photo" />
        <span className="searched-info">
          <span className="searched-tag">Top search</span>
          <b>{first.p.full_name}</b>
          <small>{first.p.club_full_name}, {first.p.position} · {first.viewers} scouts {period}</small>
          <span className="searched-bars">
            <span className="spot-legend"><span>Per game</span><span>Beats</span></span>
            {SPOT_STATS.map((key) => { const stat = statByKey(key), r = percentile(first.p, key); return r && (
              <span key={key} className="spot-bar" title={`${formatStat(stat, r.mine)} ${stat.label.toLowerCase()}: better than ${r.pct}% of regular players (40+ games, 15+ minutes)`}><span>{stat.short}</span><i><em style={{ width: `${Math.max(3, r.pct)}%` }} /></i><b>{formatStat(stat, r.mine)}</b><small>{r.pct}%</small></span>
            ); })}
            <span className="spot-note">“Beats” is the share of regular players (40+ games, 15+ minutes) he is better than.</span>
          </span>
        </span>
      </button>
      <ol className="searched-rest">
        {rest.map(({ p, viewers }, i) => (
          <li key={p.player_id}>
            <button type="button" style={teamVars(p.club_team_id)} onClick={() => open(p.player_id)}>
              <span className="searched-rank">{i + 2}</span>
              <Avatar key={p.nba_player_id} name={p.full_name} nbaPlayerId={p.nba_player_id} className="player-thumb" />
              <span className="searched-name"><b>{p.full_name}</b><small>{p.club}, {p.position}</small></span>
              <span className="searched-count"><b>{viewers}</b><small>scouts</small></span>
            </button>
          </li>
        ))}
      </ol>
    </div>
    </Band>
  );
}

/** Adds "in" to an element the first time it scrolls into view; the CSS animates from there. */
function useReveal<T extends HTMLElement = HTMLElement>() {
  const ref = useRef<T | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (!('IntersectionObserver' in window)) { el.classList.add('in'); return; }
    const seen = new IntersectionObserver((entries) => { if (entries.some((e) => e.isIntersecting)) { el.classList.add('in'); seen.disconnect(); } }, { threshold: 0.12 });
    seen.observe(el);
    return () => seen.disconnect();
  }, []);
  return ref;
}

function Reveal({ className = '', children }: { className?: string; children: ReactNode }) {
  return <div ref={useReveal<HTMLDivElement>()} className={`reveal ${className}`}>{children}</div>;
}

/** "217,398" counts up from zero the first time it is seen; people who prefer less motion see the number at once. */
function CountUp({ value }: { value: string }) {
  const target = Number(value.replace(/,/g, ''));
  const [shown, setShown] = useState(() => (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? target : 0));
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (shown === target || !ref.current) return;
    let frame = 0;
    const seen = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      seen.disconnect();
      const begin = performance.now();
      const step = (now: number) => {
        const t = Math.min(1, (now - begin) / 1400);
        setShown(Math.round(target * (1 - (1 - t) ** 3)));
        if (t < 1) frame = requestAnimationFrame(step);
      };
      frame = requestAnimationFrame(step);
    });
    seen.observe(ref.current);
    return () => { seen.disconnect(); cancelAnimationFrame(frame); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return <span ref={ref}>{shown.toLocaleString('en-US')}</span>;
}

/** A home page section: a rounded band with a soft tint in one corner, so no section sits on bare black. */
function Band({ tone, title, note, action, children }: { tone: 'warm' | 'cool' | 'violet' | 'gold' | 'neutral'; title: string; note?: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section ref={useReveal()} className={`home-band reveal ${tone}`} aria-label={title}>
      <div className="section-head"><div><h2>{title}</h2>{note && <p className="count-label">{note}</p>}</div>{action}</div>
      {children}
    </section>
  );
}

function Bars({ stat, warm }: { stat: FormStat; warm: boolean }) {
  const values = stat.games.map((v) => v ?? 0);
  const hi = Math.max(1, stat.before, ...values), lo = Math.min(0, ...values);
  const y = (v: number) => ((v - lo) / (hi - lo)) * 100;
  return (
    <span className="streak-bars" aria-hidden="true">
      <u style={{ bottom: `${y(stat.before)}%` }} />
      {values.map((v, i) => <i key={i} className={(v >= stat.before) === warm ? 'on' : ''} style={{ height: `${Math.max(4, y(v) - y(0))}%`, bottom: `${y(Math.min(0, v))}%` }} />)}
    </span>
  );
}

function HotAndCold() {
  const { byId, open, go } = useApp();
  const { data } = useApi<FormRow[]>('/form?games=10');
  const rows = useMemo(() => (data ?? []).flatMap((f) => {
    const p = byId.get(f.player_id), s = f.stats.game_score, m = f.stats.minutes;
    return p && s && m && m.before >= 20 && m.now >= 20 ? [{ p, s, change: s.now - s.before }] : [];
  }), [data, byId]);
  const hot = [...rows].filter((r) => r.change > 0).sort((a, b) => b.s.surprise - a.s.surprise).slice(0, 3);
  const cold = [...rows].filter((r) => r.change < 0).sort((a, b) => a.s.surprise - b.s.surprise).slice(0, 3);
  const side = (items: typeof rows, warm: boolean) => (
    <section className={`streak ${warm ? 'warm' : 'cool'}`}>
      <header><h3>{warm ? 'On fire' : 'Ice cold'}</h3><small>Game Score, last 10 games</small></header>
      {items.map(({ p, s, change }) => (
        <button type="button" key={p.player_id} className="streak-row" style={teamVars(p.club_team_id)} onClick={() => open(p.player_id)}>
          <Avatar key={p.nba_player_id} name={p.full_name} nbaPlayerId={p.nba_player_id} className="streak-photo" />
          <span className="streak-name"><b>{p.full_name}</b><small>{p.club} · was {s.before.toFixed(1)}</small></span>
          <Bars stat={s} warm={warm} />
          <span className="streak-value"><strong>{s.now.toFixed(1)}</strong><em>{change > 0 ? '+' : ''}{change.toFixed(1)}</em></span>
        </button>
      ))}
    </section>
  );
  return (
    <Band tone="neutral" title="Hot and cold" note="Regulars whose last 10 games stand out most from the rest of their season" action={<button type="button" className="more-link" onClick={() => go('form')}>All players<ChevronIcon /></button>}>
      {!data ? <Loading height="16rem" /> : <div className="streak-pair">{side(hot, true)}{side(cold, false)}</div>}
    </Band>
  );
}

const SLIDE_SECONDS = 7;

/** League leaders as a carousel: one category per slide, arrows, dots, swipe and the arrow keys.
 * It turns on its own until someone touches it, and not at all for people who prefer less motion. */
function LeaderCarousel({ onFull }: { onFull: (key: string) => void }) {
  const { players, totals, open } = useApp();
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const [touched, setTouched] = useState(false);
  const still = useMemo(() => Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches), []);
  const start = useRef<number | null>(null);
  const swiped = useRef(false); // a swipe that ends on a player should not open him
  const boards = useMemo(() => BOARDS.map((key) => {
    const stat = statByKey(key);
    const rows = players.filter((p) => (p.games_played ?? 0) >= 40).map((p) => ({ p, v: stat.get(p, totals[p.player_id]) })).filter((r): r is { p: PlayerDirectoryRow; v: number } => r.v != null).sort((a, b) => b.v - a.v).slice(0, 5);
    return { key, stat, rows };
  }), [players, totals]);
  const count = boards.length;
  const playing = !paused && !touched && !still;
  const go = (n: number) => { setIndex(((n % count) + count) % count); setTouched(true); };
  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => setIndex((i) => (i + 1) % count), SLIDE_SECONDS * 1000);
    return () => window.clearInterval(timer);
  }, [playing, count]);
  const current = boards[index];
  const leader = current.rows[0]?.p;
  return (
    <section
      className="carousel" style={teamVars(leader?.club_team_id)} aria-roledescription="carousel" aria-label="League leaders" tabIndex={0}
      onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)} onFocus={() => setPaused(true)} onBlur={() => setPaused(false)}
      onKeyDown={(e) => { if (e.key === 'ArrowRight') { e.preventDefault(); go(index + 1); } else if (e.key === 'ArrowLeft') { e.preventDefault(); go(index - 1); } }}
      onPointerDown={(e) => { start.current = e.clientX; }}
      onPointerUp={(e) => { if (start.current != null && Math.abs(e.clientX - start.current) > 45) { swiped.current = true; go(index + (e.clientX < start.current ? 1 : -1)); } start.current = null; }}
      onClickCapture={(e) => { if (swiped.current) { e.preventDefault(); e.stopPropagation(); swiped.current = false; } }}
    >
      <header className="carousel-head">
        <div><small>League leaders</small><h2 key={current.key} className="carousel-title">{current.stat.label}</h2></div>
        <button type="button" className="more-link" onClick={() => onFull(current.key)}>Full list<ChevronIcon /></button>
      </header>
      <div className="carousel-window">
        <div className="carousel-track" style={{ transform: `translateX(-${index * 100}%)` }}>
          {boards.map(({ key, stat, rows }, n) => {
            const [first, second, ...rest] = rows;
            return (
              <div key={key} className="carousel-slide" role="group" aria-roledescription="slide" aria-label={`${n + 1} of ${count}: ${stat.label}`} aria-hidden={n !== index}>
                {first && (
                  <button type="button" className="slide-first" style={teamVars(first.p.club_team_id)} tabIndex={n === index ? 0 : -1} onClick={() => open(first.p.player_id)}>
                    <span className="slide-logo"><TeamLogo teamId={first.p.club_team_id} size={190} /></span>
                    <span className="slide-photo-wrap"><Avatar key={first.p.nba_player_id} name={first.p.full_name} nbaPlayerId={first.p.nba_player_id} className="slide-photo" /><span className="slide-crown" title="League leader"><svg viewBox="0 0 24 16" aria-hidden="true"><path d="M2 14 1 3l6 5 5-7 5 7 6-5-1 11z" /><path d="M2 15.2h20" /></svg><span className="visually-hidden">League leader</span></span></span>
                    <span className="slide-who"><b>{first.p.full_name}</b><small><TeamLogo teamId={first.p.club_team_id} size={16} />{first.p.club_full_name}</small>{second && <em>+{formatStat(stat, first.v - second.v)} ahead of {second.p.full_name.split(' ').slice(-1)[0]}</em>}</span>
                    <span className="slide-value"><strong>{formatStat(stat, first.v)}</strong><small>{stat.short} per game</small></span>
                  </button>
                )}
                <ol className="slide-rest">
                  {[second, ...rest].filter((r) => r != null).map(({ p, v }, i) => (
                    <li key={p.player_id}>
                      <button type="button" style={teamVars(p.club_team_id)} tabIndex={n === index ? 0 : -1} onClick={() => open(p.player_id)}>
                        <span className="slide-rank">{i + 2}</span>
                        <Avatar key={p.nba_player_id} name={p.full_name} nbaPlayerId={p.nba_player_id} className="player-thumb" />
                        <span className="slide-name"><b>{p.full_name}</b><i className="slide-bar"><em style={{ width: `${first ? (v / first.v) * 100 : 0}%` }} /></i></span>
                        <b className="slide-num">{formatStat(stat, v)}</b>
                      </button>
                    </li>
                  ))}
                </ol>
              </div>
            );
          })}
        </div>
      </div>
      <footer className="carousel-controls">
        <div className="carousel-dots" role="tablist" aria-label="Categories">
          {boards.map(({ key, stat }, n) => (
            <button type="button" key={key} role="tab" aria-selected={n === index} aria-label={stat.label} title={stat.label} className={n === index ? 'on' : ''} onClick={() => go(n)}>
              {n === index && <i key={`${index}-${playing}`} className={playing ? 'run' : ''} style={{ animationDuration: `${SLIDE_SECONDS}s` }} />}
            </button>
          ))}
        </div>
        <div className="carousel-arrows">
          <button type="button" className="carousel-arrow back" aria-label="Previous category" onClick={() => go(index - 1)}><ChevronIcon /></button>
          <button type="button" className="carousel-arrow" aria-label="Next category" onClick={() => go(index + 1)}><ChevronIcon /></button>
        </div>
      </footer>
    </section>
  );
}

export function Home() {
  const { byId, loading, error, openGame, go, user } = useApp();
  const showBoard = (key: string) => { rememberFor('top', 'top-stat', key); go('top'); };
  const best = useApi<BestGame[]>('/players/best-games?limit=6');
  if (error) return <LoadError message={error} />;
  return (
    <>
      <section className="home-hero">
        <div className="home-hero-main">
          <span className="hero-kicker">The 2024-25 NBA season, in numbers</span>
          <h1>Every shot.<br />Every matchup.<br /><em>Every answer.</em></h1>
          <p>Scout any player in plain language. Each answer comes with the shots, box scores and defender matchups behind it, so you can check it yourself.</p>
          <div className="hero-actions">
            <button type="button" className="submit-button" onClick={() => go('scout')}>Ask the scout</button>
            <button type="button" className="ghost-button" onClick={() => go('players')}>Browse players</button>
          </div>
          <dl className="hero-proof">{PROOF.map(([n, label]) => <div key={label}><dt><CountUp value={n} /></dt><dd>{label}</dd></div>)}</dl>
        </div>
        {!loading && <LeaderCarousel onFull={showBoard} />}
      </section>
      {user && !loading && <Reveal><Suggested withShortlist /></Reveal>}
      {!loading && <MostSearched />}
      {!loading && <HotAndCold />}
      {!loading && <Reveal className="home-band violet"><MostViewed /></Reveal>}
      <Band tone="cool" title="Best games of the season" note="The six highest Game Scores of 2024-25">
        {best.error ? <LoadError message={best.error} /> : !best.data || loading ? <Loading height="12rem" /> : (
          <div className="best-grid">
            {best.data.map((g) => {
              const p = byId.get(g.player_id);
              return p && (
                <button type="button" className="panel best-card team-tint" style={teamVars(g.team_id)} key={`${g.player_id}${g.game_id}`} onClick={() => openGame(g.game_id)}>
                  <span className="best-top"><Avatar key={p.nba_player_id} name={p.full_name} nbaPlayerId={p.nba_player_id} className="recent-photo" /><span><b>{p.full_name}</b><small>{formatDate(g.game_date)}</small></span></span>
                  <span className="best-line"><strong>{g.points}<small>pts</small></strong><span><b>{g.rebounds}</b> reb</span><span><b>{g.assists}</b> ast</span><span><b>{g.field_goals_made}/{g.field_goals_attempted}</b> FG</span><span><b>{g.game_score.toFixed(1)}</b> Game Score</span></span>
                  <span className="best-foot"><TeamLogo teamId={g.team_id} size={26} /><b>{g.team_points}–{g.opponent_points}</b><TeamLogo teamId={g.opponent_id} size={26} /><small>{g.won ? 'Won' : 'Lost'} {g.is_home ? 'vs' : '@'} {g.opponent}</small><em className="box-link">Box score<ChevronIcon /></em></span>
                </button>
              );
            })}
          </div>
        )}
      </Band>
      {/* TODO(upcoming): needs a schedule and a game model; only the finished 2024-25 season is loaded. */}
      <Reveal className="home-band upcoming">
        <span className="upcoming-icon" aria-hidden="true" />
        <div><h2>Upcoming games</h2><p>Coming in a future update: the next games on the schedule, with a predicted winner and score for each, built from the same team and player data.</p></div>
        <span className="soon-tag">Soon</span>
      </Reveal>
    </>
  );
}
