import { useState } from 'react';
import { playerImage } from '../utils';

/** Headshot with the player's initials as the fallback. */
export function Avatar({ name, nbaPlayerId, className }: { name: string; nbaPlayerId: number; className: string }) {
  const [failed, setFailed] = useState(false);
  const words = name.split(' ');
  return (
    <span className={className} aria-hidden="true">
      {failed ? `${words[0][0]}${words.length > 1 ? words[1][0] : ''}` : <img src={playerImage(nbaPlayerId)} alt="" loading="lazy" onError={() => setFailed(true)} />}
    </span>
  );
}
