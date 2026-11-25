import { useEffect, useRef, useState } from 'react';
import { useApp } from '../AppContext';
import type { View } from '../types';

const MAIN: [View, string][] = [['home', 'Home'], ['players', 'Players'], ['top', 'Top players'], ['teams', 'Teams'], ['games', 'Games'], ['scout', 'Scout']];
const TOOLS: [View, string, string][] = [['explorer', 'Stat Explorer', 'Plot any two stats'], ['shotlab', 'Shot Lab', 'Best shooters by zone'], ['young', 'Young talent', 'Best players by age'], ['form', 'Hot and cold', 'Last 10 games'], ['lineup', 'Lineup Builder', 'Test five players']];

export function Nav({ view }: { view: View }) {
  const { go, favoriteIds, compareIds, error, user } = useApp();
  const [menu, setMenu] = useState<'tools' | 'all' | null>(null);
  const bar = useRef<HTMLElement>(null);
  useEffect(() => { setMenu(null); }, [view]);
  useEffect(() => {
    if (!menu) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === 'Escape' : !bar.current?.contains(e.target as Node)) setMenu(null);
    };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', close);
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', close); };
  }, [menu]);
  const current = view === 'team' ? 'teams' : view === 'game' ? 'games' : view;
  const pick = (v: View) => { setMenu(null); go(v); };
  const tab = (v: View, label: string, count = 0) => <button key={v} type="button" aria-current={current === v ? 'page' : undefined} className={current === v ? 'nav-tab active' : 'nav-tab'} onClick={() => pick(v)}>{label}{count > 0 && <span>{count}</span>}</button>;
  const toolActive = TOOLS.some(([v]) => v === current);
  const toolList = TOOLS.map(([v, label, text]) => <button key={v} type="button" aria-current={current === v ? 'page' : undefined} className="menu-item" onClick={() => pick(v)}><b>{label}</b><small>{text}</small></button>);
  return (
    <header className="topbar" ref={bar}>
      <button type="button" className="brand" onClick={() => pick('home')} aria-label="Scouting Console, home"><span className="brand-ball" aria-hidden="true" /><span className="brand-name">Scouting <em>Console</em></span></button>
      <nav className="main-nav" aria-label="Main">
        {MAIN.map(([v, label]) => tab(v, label))}
        <div className="nav-drop">
          <button type="button" className={toolActive ? 'nav-tab active' : 'nav-tab'} aria-expanded={menu === 'tools'} onClick={() => setMenu(menu === 'tools' ? null : 'tools')}>Analysis <i className="caret" aria-hidden="true" /></button>
          {menu === 'tools' && <div className="drop-menu">{toolList}</div>}
        </div>
      </nav>
      <div className="nav-side">
        {error && <span className="offline-note">API offline</span>}
        {tab('shortlist', 'Shortlist', favoriteIds.length)}{tab('compare', 'Compare', compareIds.length)}
        {user ? <button type="button" className="user-button" aria-current={current === 'account' ? 'page' : undefined} title={`${user.display_name}, your account`} onClick={() => pick('account')}>{user.display_name.slice(0, 1).toUpperCase()}<span className="visually-hidden"> Your account</span></button> : <button type="button" className="signin-button" onClick={() => pick('login')}>Sign in</button>}
        <button type="button" className="nav-tab menu-button" aria-expanded={menu === 'all'} onClick={() => setMenu(menu === 'all' ? null : 'all')}>Menu</button>
      </div>
      {menu === 'all' && <nav className="mobile-menu" aria-label="All pages">{MAIN.map(([v, label]) => <button key={v} type="button" className="menu-item" aria-current={current === v ? 'page' : undefined} onClick={() => pick(v)}><b>{label}</b></button>)}{toolList}</nav>}
    </header>
  );
}
