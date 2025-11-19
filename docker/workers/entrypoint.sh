#!/usr/bin/env bash
set -euo pipefail

CELERY_QUEUE="${CELERY_QUEUE:-default}"
CELERY_APP="${CELERY_APP:-ingestion.celery_app}"
CELERY_CONCURRENCY="${CELERY_CONCURRENCY:-4}"
CELERY_LOG_LEVEL="${CELERY_LOG_LEVEL:-INFO}"
CELERY_OPTS="${CELERY_OPTS:-}"

mkdir -p /etc/supervisor/conf.d

cat >/etc/supervisor/conf.d/celery.conf <<EOF
[program:celery]
command=/usr/local/bin/celery -A ${CELERY_APP} worker -Q ${CELERY_QUEUE} -n ${CELERY_QUEUE}@%%h -c ${CELERY_CONCURRENCY} -l ${CELERY_LOG_LEVEL} ${CELERY_OPTS}
directory=/app
autostart=true
autorestart=true
stopwaitsecs=10
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
EOF

exec /usr/bin/supervisord -n -c /etc/supervisor/supervisord.conf
