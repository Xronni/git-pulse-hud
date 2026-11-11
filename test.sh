#!/usr/bin/env bash
# GitPulse HUD — Test Suite Launcher
set -e
cd "$(dirname "$0")"
# Unit tests ship with the source tree only (not with release archives)
if [ -d tests ]; then
    python3 -m unittest discover -s tests
fi
python3 verify_app.py "$@"
