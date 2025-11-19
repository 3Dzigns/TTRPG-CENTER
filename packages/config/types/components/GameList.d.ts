import type { Game } from "@ttrpg-center/types";
import type { ReactNode } from "react";
export interface GameListProps {
    games: Game[];
    activeGameId?: string | null;
    onSelect?: (game: Game) => void;
    onJoinClick?: () => void;
    emptyState?: ReactNode;
    className?: string;
}
export declare function GameList({ games, activeGameId, onSelect, onJoinClick, emptyState, className }: GameListProps): any;
