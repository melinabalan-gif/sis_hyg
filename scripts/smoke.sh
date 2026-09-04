#!/usr/bin/env sh
set -eu

base_url="${HYS_SMOKE_BASE_URL:-https://localhost}"
curl_flags="--fail --silent --show-error --retry 30 --retry-delay 2 --retry-all-errors --connect-timeout 3 --max-time 10"
if [ "${HYS_SMOKE_INSECURE_LOCAL_TLS:-0}" = "1" ]; then
  curl_flags="$curl_flags --insecure"
fi

# shellcheck disable=SC2086
curl $curl_flags "$base_url/api/v1/health/live" | grep -q '"status":"ok"'
# shellcheck disable=SC2086
curl $curl_flags "$base_url/api/v1/health/ready" | grep -q '"status":"ready"'
# shellcheck disable=SC2086
curl $curl_flags "$base_url/" | grep -q 'DATOS 100 % SINTÉTICOS'

test "$(docker compose ps --status exited --services migrate)" = "migrate"
test "$(docker compose ps -a --format json migrate | grep -c '"ExitCode":0')" -ge 1

for private_endpoint in "db 5432" "seaweedfs 8333" "seaweedfs 8888" "seaweedfs 9333" "clamav 3310"; do
  set -- $private_endpoint
  for container_id in $(docker compose ps -q "$1"); do
    if docker port "$container_id" "$2/tcp" 2>/dev/null | grep -q .; then
      echo "$1:$2 no debe publicarse en el host" >&2
      exit 1
    fi
  done
done

echo "Smoke OK"
