PNPM ?= pnpm

.PHONY: dev lint test test-e2e clean caches

dev:
	$(PNPM) --filter @ttrpg-center/web dev

lint:
	$(PNPM) --filter @ttrpg-center/web lint

test:
	$(PNPM) --filter @ttrpg-center/web test

test-e2e:
	$(PNPM) --filter @ttrpg-center/web test:e2e

clean:
	$(PNPM) exec rimraf node_modules apps/web/.next apps/web/.turbo

caches:
	$(PNPM) store prune
