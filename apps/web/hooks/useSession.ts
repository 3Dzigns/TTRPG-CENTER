"use client";

import { useSessionContext } from "../components/session/session-provider";

export const useSession = () => useSessionContext();

