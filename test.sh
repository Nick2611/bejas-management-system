#!/bin/sh
set -eu

cleanup() {
  docker compose stop postgres-test >/dev/null 2>&1 || true
}

trap cleanup EXIT INT TERM

docker compose --profile test build back-test front-test
docker compose --profile test run --rm back-test
docker compose --profile test run --rm --no-deps front-test
