import { expect, test } from "@playwright/test";

const now = new Date().toISOString();

type Mutable<T> = {
  -readonly [P in keyof T]: Mutable<T[P]>;
};

const respondJson = (route: import("@playwright/test").Route, payload: unknown, status = 200) =>
  route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(payload)
  });

const playerSession = {
  id: "user-1",
  displayName: "Avery Player",
  email: "avery@example.com",
  roles: ["player"],
  avatarUrl: undefined,
  preferredTheme: "light",
  usage: {
    totalSecondsPlayed: 3600,
    monthlySessionCount: 4,
    automationCreditsRemaining: 18,
    textAssistRemaining: 12,
    audioBridgeRemaining: 2,
    discordBridgeRemaining: 5
  }
};

const gmSession = {
  id: "gm-1",
  displayName: "Morgan GM",
  email: "morgan@example.com",
  roles: ["gm"],
  avatarUrl: undefined,
  preferredTheme: "dark",
  usage: {
    totalSecondsPlayed: 8200,
    monthlySessionCount: 12,
    automationCreditsRemaining: 9
  }
};

const adminSession = {
  id: "admin-1",
  displayName: "Riley Admin",
  email: "riley@example.com",
  roles: ["admin"],
  avatarUrl: undefined,
  preferredTheme: "dark",
  usage: {
    totalSecondsPlayed: 1200,
    monthlySessionCount: 2,
    automationCreditsRemaining: 20
  }
};

const createPlayerState = () => {
  const characters = [
    {
      id: "char-1",
      name: "Lyra Stormborn",
      className: "Wizard",
      level: 5,
      ownerId: playerSession.id,
      portraitUrl: undefined,
      createdAt: now,
      updatedAt: now,
      system: "pf2e",
      activeSourceIds: ["src-arcana"],
      gameId: "game-1"
    },
    {
      id: "char-2",
      name: "Darek Ironshield",
      className: "Fighter",
      level: 4,
      ownerId: playerSession.id,
      portraitUrl: undefined,
      createdAt: now,
      updatedAt: now,
      system: "dnd-5e",
      activeSourceIds: [],
      gameId: null
    }
  ];

  const game = {
    id: "game-1",
    title: "Shattered Planes",
    summary: "Weekly campaign exploring planar rifts.",
    status: "active",
    gmId: gmSession.id,
    playerIds: [playerSession.id],
    sessionCount: 8,
    createdAt: now,
    updatedAt: now,
    inviteCode: "JOIN-12345",
    tier: "standard",
    sources: [
      {
        id: "src-arcana",
        name: "Arcane Compendium",
        category: "ruleset",
        owned: false,
        updatedAt: now
      }
    ],
    members: [
      {
        userId: playerSession.id,
        email: playerSession.email,
        displayName: playerSession.displayName,
        role: "player",
        status: "active",
        invitedAt: now,
        joinedAt: now
      },
      {
        userId: gmSession.id,
        email: gmSession.email,
        displayName: gmSession.displayName,
        role: "gm",
        status: "active",
        invitedAt: now,
        joinedAt: now
      }
    ]
  };

  const ownedSources = [
    {
      id: "src-player-owned",
      name: "Player Primer",
      category: "module",
      owned: true,
      updatedAt: now
    },
    {
      id: "src-legends",
      name: "Legends of the Realm",
      category: "campaign",
      owned: true,
      updatedAt: now
    }
  ];

  return {
    characters,
    game,
    ownedSources,
    usage: {
      scope: "user",
      id: "me",
      meter: playerSession.usage,
      updatedAt: now
    }
  };
};

const createGmState = () => {
  const game = {
    id: "game-1",
    title: "Shattered Planes",
    summary: "Weekly campaign exploring planar rifts.",
    status: "active",
    gmId: gmSession.id,
    playerIds: [playerSession.id],
    sessionCount: 8,
    createdAt: now,
    updatedAt: now,
    inviteCode: "JOIN-12345",
    tier: "standard",
    sources: [
      {
        id: "src-arcana",
        name: "Arcane Compendium",
        category: "ruleset",
        owned: false,
        updatedAt: now
      }
    ],
    members: [
      {
        userId: playerSession.id,
        email: playerSession.email,
        displayName: playerSession.displayName,
        role: "player",
        status: "active",
        invitedAt: now,
        joinedAt: now
      },
      {
        userId: gmSession.id,
        email: gmSession.email,
        displayName: gmSession.displayName,
        role: "gm",
        status: "active",
        invitedAt: now,
        joinedAt: now
      }
    ],
    allowAudioBridge: false,
    allowSummaries: false,
    allowDiscordBridge: false
  };

  const ownedSources = [
    {
      id: "src-arcana",
      name: "Arcane Compendium",
      category: "ruleset",
      owned: true,
      updatedAt: now
    },
    {
      id: "src-archives",
      name: "The Lost Archives",
      category: "module",
      owned: true,
      updatedAt: now
    }
  ];

  return {
    games: [game],
    ownedSources,
    usage: {
      scope: "game",
      id: game.id,
      meter: {
        totalSecondsPlayed: 6400,
        monthlySessionCount: 6,
        automationCreditsRemaining: 7,
        textAssistRemaining: 20
      },
      updatedAt: now
    }
  };
};

const createAdminState = () => ({
  health: {
    updatedAt: now,
    services: [
      {
        id: "cassandra",
        name: "Cassandra",
        status: "healthy",
        lastCheckedAt: now,
        region: "us-east-1"
      },
      {
        id: "mongo",
        name: "MongoDB",
        status: "degraded",
        lastCheckedAt: now,
        message: "Indexes rebuilding"
      },
      {
        id: "neo4j",
        name: "Neo4j",
        status: "healthy",
        lastCheckedAt: now
      },
      {
        id: "orchestrator",
        name: "Orchestrator",
        status: "healthy",
        lastCheckedAt: now
      }
    ]
  },
  sources: [
    {
      id: "src-codex",
      name: "Codex of Ages",
      category: "ruleset",
      owned: false,
      updatedAt: now
    },
    {
      id: "src-chronicles",
      name: "Chronicles Vol. 2",
      category: "module",
      owned: false,
      updatedAt: now
    }
  ],
  users: [
    {
      id: playerSession.id,
      displayName: playerSession.displayName,
      email: playerSession.email,
      roles: playerSession.roles,
      avatarUrl: null
    },
    {
      id: gmSession.id,
      displayName: gmSession.displayName,
      email: gmSession.email,
      roles: gmSession.roles,
      avatarUrl: null
    }
  ],
  audit: {
    entries: [
      {
        id: "audit-1",
        actor: "system",
        traceId: "trace-001",
        action: "source.update",
        scope: "catalog",
        summary: "Updated Arcane Compendium metadata",
        createdAt: now,
        metadata: {}
      }
    ],
    nextCursor: null
  }
});

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try {
      window.localStorage.clear();
    } catch {
      // ignore if localStorage unavailable in init
    }

    const instances: any[] = [];
    class FakeEventSource {
      public readonly url: string;
      public readyState = 0;
      public onopen?: (event: unknown) => void;
      public onmessage?: (event: { data: string }) => void;
      public onerror?: (event: unknown) => void;
      private listeners = new Map<string, Array<(event: any) => void>>();
      private closed = false;
      public __dispatch: (type: string, event: any) => void;

      constructor(url: string) {
        this.url = url;
        instances.push(this);
        this.__dispatch = (type: string, event: any) => {
          if (this.closed) {
            return;
          }
          if (type === "message" && typeof this.onmessage === "function") {
            this.onmessage(event);
          }
          if (type === "open" && typeof this.onopen === "function" && type === "open") {
            this.onopen(event);
          }
          if (type === "error" && typeof this.onerror === "function") {
            this.onerror(event);
          }
          const handlers = this.listeners.get(type);
          if (handlers) {
            handlers.forEach((handler) => handler(event));
          }
        };
        setTimeout(() => {
          if (!this.closed) {
            this.readyState = 1;
            this.__dispatch("open", {});
          }
        }, 0);
      }

      addEventListener(type: string, handler: (event: any) => void) {
        const list = this.listeners.get(type) ?? [];
        list.push(handler);
        this.listeners.set(type, list);
      }

      removeEventListener(type: string, handler: (event: any) => void) {
        const list = this.listeners.get(type);
        if (!list) {
          return;
        }
        this.listeners.set(
          type,
          list.filter((listener) => listener !== handler)
        );
      }

      close() {
        this.closed = true;
        this.readyState = 2;
      }
    }

    (FakeEventSource as any).__emit = (matcher: (url: string) => boolean, type: string, event: any) => {
      instances.filter((instance) => matcher(instance.url)).forEach((instance) => instance.__dispatch(type, event));
    };

    (window as unknown as { EventSource: typeof EventSource }).EventSource = FakeEventSource as unknown as typeof EventSource;
    (window as any).__emitServerEvent = (match: string | null, payload: string) => {
      const predicate =
        typeof match === "string" ? (url: string) => url.includes(match) : () => true;
      (FakeEventSource as any).__emit(predicate, "message", { data: payload });
    };
  });
});

const mockSession = async (page: import("@playwright/test").Page, session: typeof playerSession | typeof gmSession | typeof adminSession) => {
  await page.route("**/v1/me", (route) => respondJson(route, session));
};

const setupPlayerRoutes = async (
  page: import("@playwright/test").Page,
  state: Mutable<ReturnType<typeof createPlayerState>>
) => {
  await mockSession(page, playerSession);

  await page.route("**/v1/characters*", async (route) => {
    const method = route.request().method();
    if (method === "GET") {
      respondJson(route, state.characters);
      return;
    }
    if (method === "PATCH") {
      const segments = route.request().url().split("/");
      const characterId = segments[segments.length - 1];
      const body = await route.request().postDataJSON();
      const target = state.characters.find((character) => character.id === characterId);
      if (target) {
        Object.assign(target, body);
        target.updatedAt = new Date().toISOString();
      }
      respondJson(route, target ?? body);
      return;
    }
    route.fallback();
  });

  await page.route("**/v1/games*", (route) => {
    const url = route.request().url();
    const method = route.request().method();
    if (method !== "GET") {
      route.fallback();
      return;
    }
    const match = url.match(/\/v1\/games\/([^/?]+)/);
    if (match) {
      respondJson(route, state.game);
      return;
    }
    respondJson(route, [state.game]);
  });

  await page.route("**/v1/sources*", (route) => {
    const requestUrl = route.request().url();
    if (route.request().method() !== "GET") {
      route.fallback();
      return;
    }
    if (requestUrl.includes("owned=true")) {
      respondJson(route, state.ownedSources);
    } else {
      respondJson(route, []);
    }
  });

  await page.route("**/v1/usage*", (route) => {
    if (route.request().method() === "GET") {
      respondJson(route, state.usage);
    } else {
      route.fallback();
    }
  });
};

const setupGmRoutes = async (
  page: import("@playwright/test").Page,
  state: Mutable<ReturnType<typeof createGmState>>
) => {
  await mockSession(page, gmSession);

  await page.route("**/v1/games*", async (route) => {
    const method = route.request().method();
    const url = route.request().url();
    const listMatch = url.match(/\/v1\/games(?:\?|$)/);
    const detailMatch = url.match(/\/v1\/games\/([^/?]+)/);

    if (method === "GET") {
      if (detailMatch) {
        respondJson(route, state.games.find((game) => game.id === detailMatch[1]) ?? state.games[0]);
        return;
      }
      if (listMatch) {
        respondJson(route, state.games);
        return;
      }
    }

    if (method === "POST" && /\/v1\/games\/[^/]+\/sources/.test(url)) {
      const body = (await route.request().postDataJSON()) as { sourceId: string };
      const target = state.games[0];
      const source = state.ownedSources.find((owned) => owned.id === body.sourceId);
      if (source && !target.sources?.some((entry) => entry.id === source.id)) {
        target.sources = [...(target.sources ?? []), { ...source, owned: false }];
      }
      respondJson(route, target);
      return;
    }

    route.fallback();
  });

  await page.route("**/v1/sources*", (route) => {
    if (route.request().method() !== "GET") {
      route.fallback();
      return;
    }
    if (route.request().url().includes("owned=true")) {
      respondJson(route, state.ownedSources);
    } else {
      respondJson(route, state.games[0].sources ?? []);
    }
  });

  await page.route("**/v1/usage*", (route) => {
    if (route.request().method() === "GET") {
      respondJson(route, state.usage);
    } else {
      route.fallback();
    }
  });
};

const setupAdminRoutes = async (
  page: import("@playwright/test").Page,
  state: Mutable<ReturnType<typeof createAdminState>>
) => {
  await mockSession(page, adminSession);

  await page.route("**/v1/admin/health*", (route) => {
    if (route.request().method() === "GET") {
      respondJson(route, state.health);
    } else {
      route.fallback();
    }
  });

  await page.route("**/v1/sources*", (route) => {
    if (route.request().method() === "GET") {
      respondJson(route, state.sources);
    } else {
      route.fallback();
    }
  });

  await page.route("**/v1/users*", (route) => {
    if (route.request().method() === "GET") {
      respondJson(route, state.users);
    } else {
      route.fallback();
    }
  });

  await page.route("**/v1/admin/audit*", (route) => {
    if (route.request().method() === "GET") {
      respondJson(route, state.audit);
    } else {
      route.fallback();
    }
  });
};

test("sign-in button initiates SSO redirect", async ({ page }) => {
  await page.addInitScript(() => {
    (window as any).__redirects = [];
    const originalAssign = window.location.assign.bind(window.location);
    window.location.assign = (url: string | URL) => {
      (window as any).__redirects.push(String(url));
      // prevent navigation during test
      return typeof originalAssign === "function" ? undefined : undefined;
    };
  });

  await page.route("**/api/auth/start", (route) =>
    respondJson(route, { redirectTo: "https://sso.example.com/start" })
  );

  await page.goto("/auth/signin");
  await expect(page.getByRole("heading", { name: "Sign in to TTRPG Center" })).toBeVisible();

  const requestPromise = page.waitForRequest("**/api/auth/start");
  await page.getByRole("button", { name: /Continue with SSO/i }).click();
  const request = await requestPromise;

  expect(request.method()).toBe("POST");
  const body = (await request.postDataJSON()) as { provider: string; redirect: string };
  expect(body.provider).toBe("oidc");

  await expect
    .poll(() => page.evaluate(() => (window as any).__redirects?.[0] ?? null))
    .toBe("https://sso.example.com/start");
});

test("player can select sources for a character", async ({ page }) => {
  const state = createPlayerState();
  await setupPlayerRoutes(page, state);

  await page.goto("/player");
  await expect(page.getByRole("heading", { name: "Player Hub" })).toBeVisible();

  await page.getByRole("button", { name: /Lyra Stormborn/i }).click();

  const patchPromise = page.waitForRequest("**/v1/characters/char-1");
  await page.getByRole("option", { name: "Legends of the Realm" }).click();
  const patchRequest = await patchPromise;
  const patchBody = (await patchRequest.postDataJSON()) as { activeSourceIds?: string[] };
  expect(patchBody.activeSourceIds).toContain("src-legends");

  await expect(
    page.getByRole("button", { name: /Remove Legends of the Realm/i })
  ).toBeVisible();
});

test("gm can add an owned source to a game", async ({ page }) => {
  const state = createGmState();
  await setupGmRoutes(page, state);

  await page.goto("/gm");
  await expect(page.getByRole("heading", { name: "GM Hub" })).toBeVisible();

  await page.getByRole("button", { name: "Sources" }).click();

  const postPromise = page.waitForRequest("**/v1/games/game-1/sources");
  await page.getByLabel("Add source").selectOption("src-archives");
  await postPromise;

  await expect(page.getByText("The Lost Archives")).toBeVisible();
});

test("chat submit streams assistant response", async ({ page }) => {
  const state = createPlayerState();
  await setupPlayerRoutes(page, state);

  let lastQueryPayload: any = null;
  await page.route("**/v1/query", async (route) => {
    if (route.request().method() === "POST") {
      lastQueryPayload = await route.request().postDataJSON();
      respondJson(route, { requestId: "req-123", status: "queued", issuedAt: now });
      return;
    }
    route.fallback();
  });

  await page.goto("/game/game-1");
  await expect(page.getByRole("heading", { name: "Game Space" })).toBeVisible();

  await page.getByLabel("Ask the assistant").fill("Summarize the last session.");
  await page.getByRole("button", { name: "Send" }).click();

  await expect
    .poll(() => (lastQueryPayload ? lastQueryPayload.gameId : null))
    .toBe("game-1");
  expect(Array.isArray(lastQueryPayload?.sourceIds ?? [])).toBe(true);

  await page.evaluate(() =>
    (window as any).__emitServerEvent(
      "/v1/events",
      JSON.stringify({
        type: "query.status",
        requestId: "req-123",
        status: "streaming",
        delta: "Drawing on your notes..."
      })
    )
  );

  await page.evaluate(() =>
    (window as any).__emitServerEvent(
      "/v1/events",
      JSON.stringify({
        type: "query.status",
        requestId: "req-123",
        status: "completed",
        answer: "The party escaped the rift and secured the planar keystone."
      })
    )
  );

  await expect(
    page.getByText("The party escaped the rift and secured the planar keystone.")
  ).toBeVisible();
});

test("admin dashboard displays system health snapshot", async ({ page }) => {
  const state = createAdminState();
  await setupAdminRoutes(page, state);

  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "System Health" })).toBeVisible();
  await expect(page.getByText("Cassandra")).toBeVisible();
  await expect(page.getByText("MongoDB")).toBeVisible();
  await expect(page.getByRole("table", { name: "Central source catalog" })).toBeVisible();
});
