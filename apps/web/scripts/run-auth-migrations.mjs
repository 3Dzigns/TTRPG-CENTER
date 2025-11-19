import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join, dirname } from "node:path";
import { Pool } from "pg";

const connectionString = process.env.AUTH_DATABASE_URL;

if (!connectionString) {
  throw new Error("AUTH_DATABASE_URL is not configured");
}

const authPool = new Pool({
  connectionString,
  ssl:
    process.env.NODE_ENV === "production"
      ? {
          rejectUnauthorized: false
        }
      : undefined
});

async function ensureMigrationsTable() {
  await authPool.query(`
    CREATE TABLE IF NOT EXISTS auth_migrations (
      id SERIAL PRIMARY KEY,
      filename TEXT NOT NULL UNIQUE,
      executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
  `);
}

async function hasMigrationRun(filename) {
  const result = await authPool.query(
    "SELECT EXISTS (SELECT 1 FROM auth_migrations WHERE filename = $1) AS exists",
    [filename]
  );
  return result.rows[0]?.exists ?? false;
}

async function runMigration(filename, sql) {
  const client = await authPool.connect();
  try {
    await client.query("BEGIN");
    await client.query(sql);
    await client.query("INSERT INTO auth_migrations (filename) VALUES ($1)", [filename]);
    await client.query("COMMIT");
    console.log(`✔ Applied migration ${filename}`);
  } catch (error) {
    await client.query("ROLLBACK");
    console.error(`✖ Failed to apply migration ${filename}`);
    throw error;
  } finally {
    client.release();
  }
}

async function main() {
  const currentDir = dirname(fileURLToPath(import.meta.url));
  const migrationsDir = join(currentDir, "../db/migrations");
  const files = readdirSync(migrationsDir)
    .filter((file) => file.endsWith(".sql"))
    .sort();

  if (files.length === 0) {
    console.warn("No migrations found in apps/web/db/migrations");
    return;
  }

  await ensureMigrationsTable();

  for (const file of files) {
    if (await hasMigrationRun(file)) {
      console.log(`↻ Skipping already applied migration ${file}`);
      continue;
    }

    const sql = readFileSync(join(migrationsDir, file), "utf8");
    await runMigration(file, sql);
  }
}

main()
  .then(() => {
    console.log("Auth migrations complete.");
    process.exit(0);
  })
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
