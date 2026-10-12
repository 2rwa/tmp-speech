#!/usr/bin/env python3
"""Preserve existing mathematical A/B audio when republishing whole GitHub Pages."""
from pathlib import Path
from urllib.request import urlopen
import json
import re

BASE="https://2rwa.github.io/tmp-speech/"
SITE=Path("public")
try:
    with urlopen(BASE+"math/results.json",timeout=25) as f:
        previous=json.load(f)
except Exception as exc:
    print("Optional existing math results unavailable:",repr(exc),flush=True)
    previous=None

if previous:
    paths={"math/index.html","math/results.json"}
    for model in previous.get("models",[]):
        name=model.get("model","")
        if name in ("irodori-tts","irodori-tts-mf"):
            paths.add(f"math/logs/{name}-pull.log")
    for sample in previous.get("samples",[]):
        for field in ("wav","log"):
            name=sample.get(field,"")
            if re.fullmatch(r"(?:audio|logs)/[a-z0-9-]+\.(?:wav|log)",name):
                paths.add("math/"+name)
    good=bad=0
    for name in sorted(paths):
        output=SITE/name
        if output.exists(): continue
        try:
            with urlopen(BASE+name,timeout=30) as r:
                content=r.read(130*1024*1024+1)
            if len(content)>130*1024*1024: raise ValueError("oversized asset")
            output.parent.mkdir(parents=True,exist_ok=True)
            output.write_bytes(content)
            good+=1
        except Exception as exc:
            print("Could not restore:",name,repr(exc),flush=True)
            bad+=1
    print(f"Math experiment restored: {good}; missing: {bad}",flush=True)
    homepage=SITE/"index.html"
    if homepage.is_file() and (SITE/"math/index.html").is_file():
        html=homepage.read_text(encoding="utf-8")
        if 'href="math/"' not in html and "<main>" in html:
            html=html.replace("<main>",'<main><p><a href="math/">Irodori 数式記号の読み上げ比較 →</a></p>',1)
            homepage.write_text(html,encoding="utf-8")
