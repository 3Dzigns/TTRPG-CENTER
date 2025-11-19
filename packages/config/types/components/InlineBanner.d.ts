import type { ReactNode } from "react";
export type InlineBannerVariant = "info" | "success" | "warning" | "error";
export interface InlineBannerProps {
    title?: string;
    description?: ReactNode;
    variant?: InlineBannerVariant;
    traceId?: string;
    actions?: ReactNode;
    className?: string;
}
export declare function InlineBanner({ title, description, variant, traceId, actions, className }: InlineBannerProps): any;
