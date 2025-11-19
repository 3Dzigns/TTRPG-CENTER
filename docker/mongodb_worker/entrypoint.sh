#!/bin/bash
set -e

echo "Starting MongoDB in background..."
# Start MongoDB using original entrypoint in background
docker-entrypoint.sh mongod &

echo "Waiting for MongoDB to be ready..."
# Wait for MongoDB to be ready (max 60 seconds)
COUNTER=0
until mongosh --eval "db.adminCommand('ping')" &>/dev/null || [ $COUNTER -eq 60 ]; do
  printf '.'
  sleep 1
  COUNTER=$((COUNTER + 1))
done

if [ $COUNTER -eq 60 ]; then
  echo "ERROR: MongoDB failed to start within 60 seconds"
  exit 1
fi

echo "MongoDB is ready!"
echo "Starting supervisor to manage worker..."

# Start supervisor (manages worker)
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/worker.conf
