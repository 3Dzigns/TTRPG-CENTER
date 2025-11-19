import type { Character } from "@ttrpg-center/types";
import type { ReactNode } from "react";
export interface CharacterListProps {
    characters: Character[];
    selectedId?: string | null;
    onSelect?: (character: Character) => void;
    onCreateClick?: () => void;
    emptyState?: ReactNode;
    actionSlot?: ReactNode;
    className?: string;
    disableCreate?: boolean;
    disableCreateReason?: string;
}
export declare function CharacterList({ characters, selectedId, onSelect, onCreateClick, emptyState, actionSlot, className, disableCreate, disableCreateReason }: CharacterListProps): any;
