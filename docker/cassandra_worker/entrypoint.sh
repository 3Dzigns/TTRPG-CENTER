#!/bin/bash
set -e

echo "Starting Cassandra in background..."
# Start Cassandra using original entrypoint in background
docker-entrypoint.sh cassandra -f &

echo "Waiting for Cassandra to be ready..."
# Wait for Cassandra to be ready (max 120 seconds)
COUNTER=0
until cqlsh -e "SELECT release_version FROM system.local" &>/dev/null || [ $COUNTER -eq 120 ]; do
  printf '.'
  sleep 2
  COUNTER=$((COUNTER + 2))
done

if [ $COUNTER -eq 120 ]; then
  echo "ERROR: Cassandra failed to start within 120 seconds"
  exit 1
fi

echo "Cassandra is ready!"
echo "Starting supervisor to manage worker..."

# Start supervisor (manages worker)
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/worker.conf
