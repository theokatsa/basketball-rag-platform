import type { CSSProperties } from 'react';

/**
 * fill: the team's colour, lifted where the official shade would vanish on black.
 * alt: used when two teams in one game look alike.
 * edge: outline for fills that are darker than the page (the Nets are black).
 * glow: for tints, lines and gradients on the dark background.
 */
export type TeamColor = { fill: string; edge: string; glow: string };
type Brand = [fill: string, alt: string];

const BRANDS: Record<number, Brand> = {
  1610612737: ['#e03a3e', '#c1d32f'], // ATL
  1610612738: ['#0a9a4a', '#c9a24b'], // BOS
  1610612751: ['#000000', '#e9e9e9'], // BKN
  1610612766: ['#00a3b4', '#8a6bd1'], // CHA
  1610612741: ['#ce1141', '#d8d8d8'], // CHI
  1610612739: ['#bf2c68', '#fdbb30'], // CLE
  1610612742: ['#1670d0', '#b8c4ca'], // DAL
  1610612743: ['#fec524', '#4a7dc4'], // DEN
  1610612765: ['#c8102e', '#3f66e0'], // DET
  1610612744: ['#ffc72c', '#3a6fd8'], // GSW
  1610612745: ['#ce1141', '#c4ced4'], // HOU
  1610612754: ['#fdbb30', '#3a73c4'], // IND
  1610612746: ['#c8102e', '#3a6fd8'], // LAC
  1610612747: ['#8a55cf', '#fdb927'], // LAL
  1610612763: ['#6f8fd0', '#f5b112'], // MEM
  1610612748: ['#c2183f', '#f9a01b'], // MIA
  1610612749: ['#12873f', '#eee1c6'], // MIL
  1610612750: ['#2f7dc0', '#78be20'], // MIN
  1610612740: ['#b9975b', '#d0233c'], // NOP
  1610612752: ['#f58426', '#1f7fd6'], // NYK
  1610612760: ['#1a8fe0', '#ef5b2a'], // OKC
  1610612753: ['#1d86d8', '#c4ced4'], // ORL
  1610612755: ['#1f78d1', '#ed174c'], // PHI
  1610612756: ['#e56020', '#8a63d2'], // PHX
  1610612757: ['#e03a3e', '#d5d9dd'], // POR
  1610612758: ['#8c55c4', '#9aa4ab'], // SAC
  1610612759: ['#c4ced4', '#6f7a82'], // SAS
  1610612761: ['#ce1141', '#b7b7bb'], // TOR
  1610612762: ['#f4e04d', '#6cace4'], // UTA
  1610612764: ['#e31837', '#4a80c9'], // WAS
};
const PLAIN: Brand = ['#ff6a13', '#9aa4ab'];
const brand = (id: number | null | undefined) => (id != null && BRANDS[id]) || PLAIN;
const build = (fill: string): TeamColor => (fill === '#000000' ? { fill, edge: '#f2f2f2', glow: '#d5d5d8' } : { fill, edge: fill, glow: fill });

export const teamColor = (id: number | null | undefined) => build(brand(id)[0]);
export const teamAlt = (id: number | null | undefined) => build(brand(id)[1]);

type Triple = [number, number, number];
const linear = (hex: string): Triple => [1, 3, 5].map((i) => { const c = parseInt(hex.slice(i, i + 2), 16) / 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; }) as Triple;
function oklab([r, g, b]: Triple): Triple {
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459 * b), m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b), s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return [0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s, 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s, 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s];
}
const apply = (k: number[], [r, g, b]: Triple): Triple => [0, 3, 6].map((i) => Math.min(1, Math.max(0, k[i] * r + k[i + 1] * g + k[i + 2] * b))) as Triple;
/** Machado et al., severity 1: red-blind and green-blind. */
const BLIND = [[0.152286, 1.052583, -0.204868, 0.114503, 0.786281, 0.099216, -0.003882, -0.048116, 1.051998], [0.367322, 0.860646, -0.227968, 0.280085, 0.672501, 0.047413, -0.01182, 0.04294, 0.968881]];
const gap = (a: Triple, b: Triple) => { const [x, y] = [oklab(a), oklab(b)]; return Math.hypot(x[0] - y[0], x[1] - y[1], x[2] - y[2]); };
/** How far apart two colours are, for the reader who sees them worst. */
export function colorGap(a: string, b: string): number {
  const [x, y] = [linear(a), linear(b)];
  return Math.min(gap(x, y), ...BLIND.map((k) => gap(apply(k, x), apply(k, y)) * 1.6));
}

const ENOUGH = 0.17;
/** Colours for the two teams of one game. The home team keeps its own unless nothing else works. */
export function matchColors(awayId: number, homeId: number): [TeamColor, TeamColor] {
  const a = brand(awayId), h = brand(homeId);
  const options: [string, string][] = [[a[0], h[0]], [a[1], h[0]], [a[0], h[1]], [a[1], h[1]]];
  const pick = options.find(([x, y]) => colorGap(x, y) >= ENOUGH) ?? options.reduce((best, o) => (colorGap(...o) > colorGap(...best) ? o : best));
  return [build(pick[0]), build(pick[1])];
}

/** CSS variables for anything that should wear a team's colours. */
export const teamVars = (id: number | null | undefined) => ({ '--team': teamColor(id).fill, '--team-edge': teamColor(id).edge, '--team-glow': teamColor(id).glow }) as CSSProperties;
export const colorVars = (c: TeamColor) => ({ '--team': c.fill, '--team-edge': c.edge, '--team-glow': c.glow }) as CSSProperties;
export const TEAM_IDS = Object.keys(BRANDS).map(Number);
