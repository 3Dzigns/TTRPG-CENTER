# Command: Generate/Update Tests
Create or update tests for modules changed in the last commit.

## Steps
1. Identify files changed in the last commit (use `git diff --name-only HEAD~1`).
2. For each Python module changed:
   - Generate or extend pytest unit tests.
   - Cover type-safe happy paths and edge/error cases.
   - Add integration tests for ingestion pipeline, status feeds, and RAG retrieval if applicable.
3. Run the full test suite (`pytest`) locally.
4. Collect results:
   - Report pass/fail summary in console.
   - Save new/updated tests into `tests/` with meaningful filenames.
   - Place fixtures under `tests/fixtures/` if needed.

## Definition of Done
- New tests are deterministic and idempotent.
- All tests pass locally (`pytest -q` returns green).
- Coverage improves or at least does not regress.
- Relevant integration points (ingest, status, RAG) are exercised.
