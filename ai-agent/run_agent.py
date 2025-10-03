#!/usr/bin/env python
"""Compatibility wrapper to execute the CLI script."""

from scripts.run_agent import main

if __name__ == "__main__":
    raise SystemExit(main())
