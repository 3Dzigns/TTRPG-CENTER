"use client";

import { useEffect } from "react";
import type { UserRole } from "@ttrpg-center/types";
import { useAuthStore } from "../stores/auth-store";

export const useRole = (roles: UserRole[] | undefined) => {
  const selectedRole = useAuthStore((state) => state.selectedRole);
  const setSelectedRole = useAuthStore((state) => state.setSelectedRole);

  useEffect(() => {
    if (!roles || roles.length === 0) {
      return;
    }
    if (!selectedRole || !roles.includes(selectedRole)) {
      setSelectedRole(roles[0]);
    }
  }, [roles, selectedRole, setSelectedRole]);

  return {
    role: selectedRole ?? (roles && roles.length > 0 ? roles[0] : null),
    setRole: setSelectedRole
  };
};
