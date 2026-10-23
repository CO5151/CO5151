#!/usr/bin/env python3
"""Report the first lines where brace balance goes negative in a .tex file."""

from __future__ import annotations

import sys
from pathlib import Path

path = Path(sys.argv[1])
depth = 0
for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
    if line.lstrip().startswith("%"):
        continue
    for ch in line:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
    if depth < 0:
        print(f"line {i}: depth={depth}  {line[:110]}")
        depth = 0
print("final depth:", depth)
