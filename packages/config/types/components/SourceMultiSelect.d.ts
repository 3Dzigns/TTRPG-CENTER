import type { Source } from "@ttrpg-center/types";
import { type ReactNode } from "react";
export interface SourceMultiSelectProps {
    sources: Source[];
    selectedIds: string[];
    onChange: (next: string[]) => void;
    ownedSourceIds?: string[];
    selectedLabel?: string;
    renderFooter?: ReactNode;
    className?: string;
}
export declare function SourceMultiSelect({ sources, selectedIds, onChange, ownedSourceIds, selectedLabel, renderFooter, className }: SourceMultiSelectProps): any;
