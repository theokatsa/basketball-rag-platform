import { loadStored, saveStored } from './utils';

const VISITOR_KEY = 'basketball-scouting-visitor';
const KEEP_KEY = 'basketball-scouting-keep-questions';

/** A random id (RFC 4122 version 4). */
export function randomId(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  // Pages served over plain http (another computer on the network) have no randomUUID.
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, '0')).join('');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

/** A random number kept by this browser, so one person's feedback can be grouped without knowing who it is. */
export function visitorId(): string {
  let id = loadStored<string | null>(VISITOR_KEY, null);
  if (!id) { id = randomId(); saveStored(VISITOR_KEY, id); }
  return id;
}

/** Whether questions asked in this browser are kept for the evaluation (the default) or not. */
export const keepsQuestions = () => loadStored<boolean>(KEEP_KEY, true);
export const setKeepsQuestions = (keep: boolean) => saveStored(KEEP_KEY, keep);
