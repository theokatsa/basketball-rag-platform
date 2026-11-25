import type { ShotRecord } from '../types';
import { zoneOf } from './CourtZones';
import type { ZoneMap } from './CourtZones';

export type HeatKind = 'volume' | 'accuracy';
/** The court rectangle in shot coordinates, a tenth of a foot per unit. */
const X0 = -250, Y0 = -52, WIDTH = 500, HEIGHT = 470, CELL = 4;
const COLS = WIDTH / CELL, ROWS = Math.ceil(HEIGHT / CELL);
const SCALE = 6;

type Stop = [number, number, number, number, number]; // position, r, g, b, alpha
const FIRE: Stop[] = [[0, 40, 10, 4, 0], [0.12, 74, 18, 6, 0.42], [0.3, 140, 36, 6, 0.8], [0.52, 224, 78, 8, 0.93], [0.74, 255, 138, 28, 0.97], [0.9, 255, 204, 84, 0.98], [1, 255, 246, 214, 1]];
const BLUE = [58, 122, 214], GREY = [122, 114, 106], ORANGE = [255, 106, 19];

const isThree = (s: ShotRecord) => s.shot_type.startsWith('3');

/** Gaussian blur in two passes. */
function blur(source: Float32Array, sigma: number): Float32Array {
  const reach = Math.ceil(sigma * 3);
  const kernel = Array.from({ length: reach * 2 + 1 }, (_, i) => Math.exp(-((i - reach) ** 2) / (2 * sigma * sigma)));
  const pass = (input: Float32Array, sideways: boolean) => {
    const out = new Float32Array(COLS * ROWS);
    for (let r = 0; r < ROWS; r++) for (let c = 0; c < COLS; c++) {
      let total = 0, weight = 0;
      for (let k = -reach; k <= reach; k++) {
        const cc = sideways ? c + k : c, rr = sideways ? r : r + k;
        if (cc < 0 || rr < 0 || cc >= COLS || rr >= ROWS) continue;
        total += input[rr * COLS + cc] * kernel[k + reach]; weight += kernel[k + reach];
      }
      out[r * COLS + c] = total / weight;
    }
    return out;
  };
  return pass(pass(source, true), false);
}

function ramp(t: number): [number, number, number, number] {
  const i = Math.max(1, FIRE.findIndex((s) => s[0] >= t));
  const [a, b] = [FIRE[i - 1], FIRE[i]];
  const k = Math.min(1, Math.max(0, (t - a[0]) / (b[0] - a[0])));
  return [1, 2, 3, 4].map((n) => a[n] + (b[n] - a[n]) * k) as [number, number, number, number];
}

/** Paint the shots as a smooth picture: how often (volume) or how well against the league (accuracy). */
export function heatImage(shots: ShotRecord[], kind: HeatKind, league: ZoneMap | null): string | null {
  const list = shots.filter((s) => s.loc_y < Y0 + HEIGHT && Math.abs(s.loc_x) <= 250);
  if (list.length < 5) return null;
  const count = new Float32Array(COLS * ROWS), gain = new Float32Array(COLS * ROWS);
  for (const s of list) {
    const cell = Math.min(ROWS - 1, Math.max(0, Math.floor((s.loc_y - Y0) / CELL))) * COLS + Math.min(COLS - 1, Math.max(0, Math.floor((s.loc_x - X0) / CELL)));
    const base = league?.get(zoneOf(s.loc_x, s.loc_y, isThree(s))), worth = isThree(s) ? 3 : 2;
    count[cell] += 1;
    gain[cell] += (s.shot_made ? worth : 0) - (base ? (base.made / base.att) * worth : 1.1);
  }
  // Fewer shots need a wider brush.
  const narrow = Math.min(4.4, 2.4 + 24 / Math.sqrt(list.length)), sigma = kind === 'accuracy' ? narrow + 1.6 : narrow;
  const spread = blur(count, narrow);
  const density = kind === 'accuracy' ? blur(count, sigma) : spread, value = blur(gain, sigma);
  let top = 1e-6;
  for (const v of spread) if (v > top) top = v;
  const unit = 1 / (2 * Math.PI * sigma * sigma); // the height of a single shot
  // A log scale: the rim is the brightest spot without washing out the rest of the court.
  const field = spread.map((v) => Math.log1p((v / top) * 150) / Math.log(151));

  const canvas = document.createElement('canvas');
  canvas.width = COLS * SCALE; canvas.height = ROWS * SCALE;
  const context = canvas.getContext('2d');
  if (!context) return null;
  const image = context.createImageData(canvas.width, canvas.height);
  const sample = (grid: Float32Array, x: number, y: number) => {
    const c = Math.min(COLS - 1.001, Math.max(0, x)), r = Math.min(ROWS - 1.001, Math.max(0, y));
    const c0 = Math.floor(c), r0 = Math.floor(r), u = c - c0, v = r - r0;
    const at = (cc: number, rr: number) => grid[Math.min(ROWS - 1, rr) * COLS + Math.min(COLS - 1, cc)];
    return (at(c0, r0) * (1 - u) + at(c0 + 1, r0) * u) * (1 - v) + (at(c0, r0 + 1) * (1 - u) + at(c0 + 1, r0 + 1) * u) * v;
  };
  for (let py = 0; py < canvas.height; py++) for (let px = 0; px < canvas.width; px++) {
    const x = (px + 0.5) / SCALE - 0.5, y = (py + 0.5) / SCALE - 0.5, o = (py * canvas.width + px) * 4;
    const t = sample(field, x, y);
    if (t < 0.05) continue;
    if (kind === 'volume') {
      const [r, g, b, a] = ramp(t);
      image.data.set([r, g, b, a * 255], o);
    } else {
      const d = sample(density, x, y);
      const worth = sample(value, x, y) / (d + unit * 9); // nine average shots mixed in
      const k = Math.max(-1, Math.min(1, worth / 0.22)), end = k < 0 ? BLUE : ORANGE, m = Math.abs(k) ** 0.8;
      image.data.set([...GREY.map((c, i) => c + (end[i] - c) * m), Math.min(1, Math.max(0, (t - 0.1) * 3)) * (0.5 + 0.48 * m) * 255], o);
    }
  }
  context.putImageData(image, 0, 0);
  return canvas.toDataURL('image/png');
}
export const HEAT_BOX = { x: X0, y: Y0, width: COLS * CELL, height: ROWS * CELL };
