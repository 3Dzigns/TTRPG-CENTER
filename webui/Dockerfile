# ==============================================
# Stage 1: Install workspace dependencies
# ==============================================
FROM node:20-alpine AS deps
WORKDIR /app

RUN corepack enable && corepack prepare pnpm@9.10.0 --activate

COPY pnpm-workspace.yaml package.json pnpm-lock.yaml ./
COPY apps/web/package.json ./apps/web/package.json
COPY packages/api/package.json ./packages/api/package.json
COPY packages/types/package.json ./packages/types/package.json
COPY packages/ui/package.json ./packages/ui/package.json
COPY packages/config/package.json ./packages/config/package.json

RUN pnpm install --no-frozen-lockfile

# ==============================================
# Stage 2: Build Next.js application
# ==============================================
FROM node:20-alpine AS builder
WORKDIR /app

RUN corepack enable && corepack prepare pnpm@9.10.0 --activate

COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/pnpm-workspace.yaml /app/package.json /app/pnpm-lock.yaml ./
COPY tsconfig*.json ./
COPY apps ./apps
COPY packages ./packages

RUN pnpm install --frozen-lockfile --offline

ARG NEXT_PUBLIC_API_BASE=/api/v1
ARG NEXT_PUBLIC_API_BASE_URL=
ENV NEXT_PUBLIC_API_BASE=${NEXT_PUBLIC_API_BASE}
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
ENV NEXT_TELEMETRY_DISABLED=1

RUN pnpm --filter @ttrpg-center/types build && \
    pnpm --filter @ttrpg-center/config build && \
    pnpm --filter @ttrpg-center/ui --filter @ttrpg-center/api build && \
    pnpm --filter @ttrpg-center/web build

# ==============================================
# Stage 3: Production runtime
# ==============================================
FROM node:20-alpine AS runner
WORKDIR /app

RUN corepack enable && corepack prepare pnpm@9.10.0 --activate

ENV PNPM_HOME=/home/node/.local/share/pnpm
ENV PATH=${PNPM_HOME}:${PATH}

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000

ARG AUTH_DATABASE_URL=""
ENV AUTH_DATABASE_URL=${AUTH_DATABASE_URL}

COPY --from=deps --chown=node:node /app/node_modules ./node_modules
COPY --from=deps --chown=node:node /app/apps/web/node_modules ./apps/web/node_modules
COPY --from=builder --chown=node:node /app/pnpm-workspace.yaml ./pnpm-workspace.yaml
COPY --from=builder --chown=node:node /app/package.json ./package.json
COPY --from=builder --chown=node:node /app/apps/web/package.json ./apps/web/package.json
COPY --from=builder --chown=node:node /app/apps/web/.next ./apps/web/.next
COPY --from=builder --chown=node:node /app/apps/web/public ./apps/web/public
COPY --from=builder --chown=node:node /app/apps/web/scripts ./apps/web/scripts

EXPOSE 3000

USER node

CMD ["sh", "-c", "node apps/web/scripts/ensure-client-manifest.cjs && pnpm --filter @ttrpg-center/web start"]
