import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { Pool } from "pg";

const connectionString = process.env.AUTH_DATABASE_URL;

if (!connectionString) {
  throw new Error("AUTH_DATABASE_URL is not configured");
}

const pool = new Pool({
  connectionString,
  ssl:
    process.env.NODE_ENV === "production"
      ? {
          rejectUnauthorized: false
        }
      : undefined
});

async function main() {
  const currentDir = dirname(fileURLToPath(import.meta.url));
  const seedsDir = join(currentDir, "../db/seeds");

  const files = readdirSync(seedsDir)
    .filter((file) => file.endsWith(".sql"))
    .sort();

  if (files.length === 0) {
    console.warn("No seed files found.");
    return;
  }

  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    for (const file of files) {
      const sql = readFileSync(join(seedsDir, file), "utf8");
      console.log(`Applying seed ${file}`);
      await client.query(sql);
    }
    await client.query("COMMIT");
    console.log("Seed data applied.");
  } catch (error) {
    await client.query("ROLLBACK");
    console.error("Failed to seed auth database.");
    throw error;
  } finally {
    client.release();
    await pool.end();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
