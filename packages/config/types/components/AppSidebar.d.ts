import type { PropsWithChildren, ReactNode } from "react";
import type { UserRole } from "@ttrpg-center/types";
export interface SidebarNavItem {
    label: string;
    href: string;
    icon?: ReactNode;
    roles?: UserRole[];
}
export interface AppSidebarProps extends PropsWithChildren {
    role: UserRole;
    items: SidebarNavItem[];
    footer?: ReactNode;
    currentPath?: string;
    className?: string;
}
export declare function AppSidebar({ role, items, footer, currentPath, className, children }: AppSidebarProps): any;
