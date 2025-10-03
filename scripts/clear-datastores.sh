#!/bin/bash
# Script to clear all datastores for clean ingestion run
# Usage: ./scripts/clear-datastores.sh

set -e

echo "🧹 Clearing TTRPG Center Datastores..."
echo "========================================"

# Clear MongoDB
echo ""
echo "📦 Clearing MongoDB collections..."
docker exec ttrpg-mongo-dev mongosh ttrpg_dev --eval '
db.getCollectionNames().forEach(function(collName) {
    if (collName !== "system.indexes") {
        print("Dropping collection: " + collName);
        db[collName].drop();
    }
});
print("MongoDB cleared successfully");
'

# Clear Cassandra
echo ""
echo "🗄️  Clearing Cassandra keyspace..."
docker exec ttrpg-cassandra-dev cqlsh -e "
DROP KEYSPACE IF EXISTS ttrpg_dev;
CREATE KEYSPACE ttrpg_dev WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};
" && echo "Cassandra keyspace cleared and recreated successfully"

# Clear Redis
echo ""
echo "💾 Clearing Redis cache..."
docker exec ttrpg-redis-dev redis-cli FLUSHALL && echo "Redis cleared successfully"

# Clear Neo4J (if running)
echo ""
echo "🕸️  Checking for Neo4J..."
if docker ps --format '{{.Names}}' | grep -q "ttrpg-neo4j-dev"; then
    echo "Clearing Neo4J database..."
    docker exec ttrpg-neo4j-dev cypher-shell -u neo4j -p password "
    MATCH (n) DETACH DELETE n;
    " && echo "Neo4J cleared successfully"
else
    echo "Neo4J not running, skipping..."
fi

echo ""
echo "✅ All datastores cleared and ready for clean ingestion run!"
echo ""
echo "You can now:"
echo "  1. Access Admin UI at http://localhost:8000"
echo "  2. Upload PDFs via the ingestion page"
echo "  3. Run Selective Ingestion jobs"
