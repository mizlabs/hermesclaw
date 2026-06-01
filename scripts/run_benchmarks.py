#!/usr/bin/env python3
"""Run security benchmarks and print summary table."""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/benchmarks/", "-v", "-s", "--tb=short"],
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
