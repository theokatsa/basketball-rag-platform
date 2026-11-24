import { Avatar } from './Avatar';

type Props = { playerId: number; name: string; nbaPlayerId?: number; onOpen: (playerId: number) => void };

export function PlayerLink({ playerId, name, nbaPlayerId, onOpen }: Props) {
  return (
    <button type="button" className="player-link" title={name} onClick={() => onOpen(playerId)}>
      {nbaPlayerId != null && <Avatar key={nbaPlayerId} name={name} nbaPlayerId={nbaPlayerId} className="player-thumb" />}
      <span className="player-name">{name}</span>
    </button>
  );
}
