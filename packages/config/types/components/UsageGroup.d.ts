import type { ReactNode } from "react";
import { type UsageMeterProps } from "./UsageMeter";
export interface UsageGroupProps {
    title: string;
    description?: string;
    items: UsageMeterProps[];
    footer?: ReactNode;
    className?: string;
}
export declare function UsageGroup({ title, description, items, footer, className }: UsageGroupProps): any;
