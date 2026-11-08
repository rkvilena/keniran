#!/usr/bin/env bash
# Capture Linux hardware-audit fixtures for the offline test suite.
#
# Run inside Linux or WSL2 (WSL2 is the reference environment):
#     bash scripts/capture_linux_fixtures.sh
#
# Snapshots /proc/cpuinfo and /proc/meminfo into tests/fixtures/linux/. The
# pytest suite never invokes this script; it only reads the recorded files, so
# tests stay OS-agnostic.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fixtures_dir="${repo_root}/tests/fixtures/linux"

if [[ ! -r /proc/cpuinfo || ! -r /proc/meminfo ]]; then
    printf 'error: /proc/cpuinfo and /proc/meminfo are required; run this inside Linux/WSL\n' >&2
    exit 1
fi

mkdir -p "${fixtures_dir}"
cp /proc/cpuinfo "${fixtures_dir}/proc_cpuinfo.txt"
cp /proc/meminfo "${fixtures_dir}/proc_meminfo.txt"

printf 'captured %s\n' "${fixtures_dir}/proc_cpuinfo.txt"
printf 'captured %s\n' "${fixtures_dir}/proc_meminfo.txt"
