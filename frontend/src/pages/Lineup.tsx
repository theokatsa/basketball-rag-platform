import { useEffect, useState } from 'react';
import { useApp } from '../AppContext';
import { Avatar } from '../components/Avatar';
import { LoadError, Loading, PageHead, PlayerCell, TeamLogo } from '../components/Common';
import { Dropdown, useTeamList } from '../components/Dropdown';
import { CloseIcon } from '../components/Icons';
import { LineupReport } from '../components/LineupReport';
import type { LineupResult } from '../types';
import { teamVars } from '../teamColors';
import { send } from '../useApi';
import { usePersisted } from '../usePersisted';

const EMPTY: (number | null)[] = [null, null, null, null, null];
const QUICK = ['BOS', 'OKC', 'CLE', 'DEN', 'NYK', 'LAL'];
/** The half court in tenths of a foot, hoop at 0,0: 50 ft wide, 47 ft from baseline to half court. */
const VIEW = { x: -252, y: -54, w: 504, h: 474 };
const at = (x: number, y: number) => ({ left: `${((x - VIEW.x) / VIEW.w) * 100}%`, top: `${((y - VIEW.y) / VIEW.h) * 100}%` });
/** Each place: name, position for the player list, short name, spot on the court. */
const SPOTS: [string, string, string, number, number][] = [['Point guard', 'Guard', 'PG', 0, 300], ['Shooting guard', 'Guard', 'SG', -165, 220], ['Small forward', 'Forward', 'SF', 165, 220], ['Power forward', 'Forward', 'PF', -150, 70], ['Center', 'Center', 'C', 70, 25]];
const surname = (name: string) => name.split(' ').slice(1).join(' ') || name;

function Court() {
  return (
    <svg viewBox={`${VIEW.x} ${VIEW.y} ${VIEW.w} ${VIEW.h}`} aria-hidden="true">
      <rect x={-80} y={-52} width={160} height={190} className="lu-paint" />
      <g className="lu-lines">
        <rect x={-250} y={-52} width={500} height={470} />
        <rect x={-80} y={-52} width={160} height={190} />
        <rect x={-60} y={-52} width={120} height={190} />
        <path d="M-60 138A60 60 0 0 0 60 138" />
        <path d="M-60 138A60 60 0 0 1 60 138" className="dash" />
        <path d="M-40 -10V0A40 40 0 0 0 40 0V-10" />
        <path d="M-220 -52V89.5A237.5 237.5 0 0 0 220 89.5V-52" />
        <path d="M-60 418A60 60 0 0 1 60 418" />
        <path d="M-20 418A20 20 0 0 1 20 418" />
        <line x1={-30} x2={30} y1={-12} y2={-12} className="board" />
      </g>
      <circle r={7.5} className="lu-rim" />
    </svg>
  );
}

export function Lineup() {
  const { byId, players, loading, error, browse } = useApp();
  const teams = useTeamList();
  const [slots, setSlots] = usePersisted<(number | null)[]>('lineup', EMPTY);
  const [result, setResult] = useState<{ key: string; data: LineupResult | null; error: string | null } | null>(null);
  const ids = slots.filter((id): id is number => id != null);
  const key = ids.length === 5 ? ids.join(',') : '';
  useEffect(() => {
    if (!key) return;
    let cancelled = false;
    send<LineupResult>('POST', '/insights/lineup', { player_ids: key.split(',').map(Number) })
      .then((data) => { if (!cancelled) setResult({ key, data, error: null }); })
      .catch((err: Error) => { if (!cancelled) setResult({ key, data: null, error: err.message }); });
    return () => { cancelled = true; };
  }, [key]);
  if (error) return <LoadError message={error} />;
  const current = result?.key === key ? result : null;
  const data = current?.data;
  const set = (i: number, id: number | null) => setSlots(slots.map((v, k) => (k === i ? id : v)));
  const pick = (i: number) => browse({ title: `Choose a ${SPOTS[i][0].toLowerCase()}`, max: 1, position: SPOTS[i][1], exclude: ids.filter((id) => id !== slots[i]), onDone: ([id]) => set(i, id) });
  const many = () => browse({ title: 'Choose five players', max: 5, min: 1, confirm: 'Use these players', selected: ids, onDone: (list) => setSlots(EMPTY.map((_, i) => list[i] ?? null)) });
  const fromTeam = (name: string) => {
    const top = players.filter((p) => p.club_full_name === name && (p.games_played ?? 0) >= 20).sort((a, b) => (b.minutes ?? 0) - (a.minutes ?? 0)).slice(0, 5);
    const size = (p: (typeof top)[number]) => { const list = (p.position ?? '').split('-').map((x) => ['Guard', 'Forward', 'Center'].indexOf(x)); return list.reduce((s, n) => s + n, 0) / list.length; };
    setSlots(EMPTY.map((_, i) => top.sort((a, b) => size(a) - size(b))[i]?.player_id ?? null));
  };
  return (
    <>
      <PageHead title="Lineup Builder" intro="Put five players on the floor and see how the group should play.">
        <div className="panel-tools">
          <Dropdown label="Load a team" value="" options={[{ value: '', label: 'Load a team’s five' }, ...teams.map((t) => ({ value: t.name, label: t.name, note: t.abbr, icon: <TeamLogo teamId={t.id} size={24} /> }))]} onChange={(v) => v && fromTeam(v)} search="Search teams" wide />
          <button type="button" className="submit-button" onClick={many}>Choose from a list</button>
          {ids.length > 0 && <button type="button" className="ghost-button" onClick={() => setSlots(EMPTY)}>Clear</button>}
        </div>
      </PageHead>
      <div className="lu-stage">
        <section className="lu-court" aria-label="The five places">
          <Court />
          {slots.map((id, i) => {
            const p = id != null ? byId.get(id) : undefined;
            const [label, , short, x, y] = SPOTS[i];
            return (
              <div className={`lu-token ${p ? 'filled' : ''}`} key={i} style={{ ...at(x, y), ...(p ? teamVars(p.club_team_id) : {}) }}>
                <button type="button" className="lu-token-face" title={p ? `${p.full_name}: change player` : `Add a ${label.toLowerCase()}`} aria-label={p ? `Change ${p.full_name}` : `Add a ${label.toLowerCase()}`} onClick={() => pick(i)}>
                  {p ? <Avatar key={p.nba_player_id} name={p.full_name} nbaPlayerId={p.nba_player_id} className="lu-token-photo" /> : <span className="lu-token-plus" aria-hidden="true">+</span>}
                  <span className="lu-token-slot">{short}</span>
                </button>
                <span className="lu-token-name">{p ? surname(p.full_name) : label}</span>
              </div>
            );
          })}
        </section>
        <section className="panel lu-roster" aria-label="Your five">
          <div className="panel-header"><div><h2>Your five</h2><p>{ids.length === 5 ? 'Click a player on the court or here to swap them.' : `${ids.length} of 5 chosen. Click a place to add a player.`}</p></div></div>
          <ol>
            {slots.map((id, i) => {
              const p = id != null ? byId.get(id) : undefined;
              const [label, , short] = SPOTS[i];
              return (
                <li key={i} className={p ? 'filled' : ''} style={p ? teamVars(p.club_team_id) : undefined}>
                  <span className="lu-roster-slot" title={label}>{short}</span>
                  {p ? (
                    <>
                      <PlayerCell player={p} />
                      <span className="floor-line"><span><b>{p.points?.toFixed(1)}</b>PTS</span><span><b>{p.rebounds?.toFixed(1)}</b>REB</span><span><b>{p.assists?.toFixed(1)}</b>AST</span></span>
                      <span className="lu-roster-actions"><button type="button" className="text-button" onClick={() => pick(i)}>Change</button><button type="button" className="icon-button small" aria-label={`Remove ${p.full_name}`} onClick={() => set(i, null)}><CloseIcon /></button></span>
                    </>
                  ) : <button type="button" className="lu-roster-add" onClick={() => pick(i)}><span aria-hidden="true">+</span> Add a {label.toLowerCase()}</button>}
                </li>
              );
            })}
          </ol>
        </section>
      </div>
      {loading ? <Loading /> : !key ? (
        <div className="empty-state lineup-empty">
          <p>{5 - ids.length} more {5 - ids.length === 1 ? 'player' : 'players'} to go.</p>
          <small>Click a place on the floor, choose from a list, or start from a team&apos;s most-used five. The analysis appears once all five places are filled.</small>
          {ids.length === 0 && <div className="quick-teams">{QUICK.map((abbr) => { const t = teams.find((x) => x.abbr === abbr); return t && <button type="button" key={abbr} className="chip quick-team" onClick={() => fromTeam(t.name)}><TeamLogo teamId={t.id} size={18} />{t.name}</button>; })}</div>}
        </div>
      ) : current?.error ? <p className="status error" role="alert">{current.error}</p> : !data ? <Loading height="30rem" /> : (
        <LineupReport data={data} order={ids} />
      )}
    </>
  );
}
