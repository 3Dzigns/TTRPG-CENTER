import type { ReactNode } from "react";
export type ThemePreference = "light" | "dark" | "system";
export interface TopNavItem {
    label: string;
    href: string;
}
export interface TopNavProps {
    brand?: ReactNode;
    navItems?: TopNavItem[];
    onThemeToggle?: (next: ThemePreference) => void;
    theme?: ThemePreference;
    actions?: ReactNode;
    currentPath?: string;
    className?: string;
}
export declare function TopNav({ brand, navItems, onThemeToggle, theme, actions, currentPath, className }: TopNavProps): any;
