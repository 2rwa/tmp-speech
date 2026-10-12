#!/usr/bin/env python3
"""Restore known, already-published CPU/long results before a full-site Pages deploy."""
from pathlib import Path
from urllib.request import urlopen
import sys

base = "https://2rwa.github.io/tmp-speech/"
models = ("irodori-tts-mf", "irodori-tts")
short = ["index.html", "results.json"]
long = ["long/index.html", "long/results.json", "long/normalized.txt", "long/source.json"]
for model in models:
    for sample in ("short", "medium"):
        short.extend((f"audio/{model}-{sample}.wav", f"logs/{model}-{sample}.log"))
    short.append(f"logs/{model}-pull.log")
    long.extend((f"long/{model}.mp3", f"long/{model}.log", f"long/{model}-pull.log"))
files = long if "--long-only" in sys.argv else short + long
hits, misses = 0, 0
for name in files:
    path = Path("public") / name
    if path.exists():
        continue
    try:
        with urlopen(base + name, timeout=25) as response:
            data = response.read(120 * 1024 * 1024 + 1)
        if len(data) > 120 * 1024 * 1024:
            raise ValueError("Too large")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        hits += 1
    except Exception as ex:
        print("Previous Pages not available:", name, str(ex), flush=True)
        misses += 1
print("Restored", hits, "previous assets; missing", misses)
