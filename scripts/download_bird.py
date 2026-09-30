#!/usr/bin/env python3
"""Download the public BIRD dev set. Does not run during tests."""

from __future__ import annotations

from mm.data.download import main

if __name__ == "__main__":
    raise SystemExit(main())
