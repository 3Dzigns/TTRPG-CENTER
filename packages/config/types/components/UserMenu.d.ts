import type { User, UserRole } from "@ttrpg-center/types";
import type { ReactNode } from "react";
export interface UserMenuProps {
    user: Pick<User, "displayName" | "email" | "avatarUrl" | "roles">;
    onSignOut?: () => void;
    onManageAccount?: () => void;
    onRoleChange?: (role: UserRole) => void;
    selectedRole?: UserRole | null;
    className?: string;
    trigger?: ReactNode;
}
export declare function UserMenu({ user, onSignOut, onManageAccount, onRoleChange, selectedRole, className, trigger }: UserMenuProps): any;
