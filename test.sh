#!/usr/bin/env bash
# GitPulse HUD — Test Suite Launcher
set -e
cd "$(dirname "$0")"
python3 verify_app.py "$@"
