import type { ReactNode } from "react";
export interface ErrorBoundaryCardProps {
    title?: string;
    description?: ReactNode;
    traceId?: string;
    onRetry?: () => void;
    retryLabel?: string;
    retryDisabled?: boolean;
    actions?: ReactNode;
    className?: string;
    footer?: ReactNode;
}
/**
 * Displays a consistent critical-error surface that surfaces trace identifiers
 * and recommended remediation actions. Intended for blocking failures where
 * inline banners are insufficient.
 */
export declare function ErrorBoundaryCard({ title, description, traceId, onRetry, retryLabel, retryDisabled, actions, className, footer }: ErrorBoundaryCardProps): any;
