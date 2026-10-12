#!/usr/bin/env python3
"""Irodori-TTS formula pronunciation A/B experiment using speech.cpp CPU."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from subprocess import run, TimeoutExpired
from html import escape
import json
import os
import platform
import time
import wave
import math
import struct

ROOT = Path("public")
OUT = ROOT / "math"
AUDIO = OUT / "audio"
LOGS = OUT / "logs"
for d in (AUDIO, LOGS):
    d.mkdir(parents=True, exist_ok=True)
CASES = json.loads(Path("math-pronunciation/cases.json").read_text(encoding="utf-8"))
MODELS = [("irodori-tts-mf", 4, [c["id"] for c in CASES]),
          ("irodori-tts", 16, ["fraction", "integral"])]
THREADS = max(1, min(4, len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count() or 2))

def esc(v):
    return escape(str(v), quote=True)

def timed(cmd, timeout):
    started = time.monotonic()
    try:
        p = run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return {"exit_code": p.returncode, "elapsed_s": round(time.monotonic()-started, 3),
                "stdout": p.stdout[-12000:], "stderr": p.stderr[-12000:]}
    except TimeoutExpired as e:
        def dec(v):
            return v.decode("utf-8", "replace") if isinstance(v, bytes) else v or ""
        return {"exit_code": None, "elapsed_s": round(time.monotonic()-started, 3),
                "stdout": dec(e.stdout)[-12000:], "stderr": dec(e.stderr)[-12000:], "error": "timeout"}
    except OSError as e:
        return {"exit_code": None, "elapsed_s": round(time.monotonic()-started, 3),
                "stdout": "", "stderr": repr(e), "error": "exec failed"}

def save_log(ident, result):
    (LOGS / (ident + ".log")).write_text(
        json.dumps({k:v for k,v in result.items() if k not in ("stdout","stderr")}, ensure_ascii=False)
        + "\nSTDOUT\n" + result["stdout"] + "\nSTDERR\n" + result["stderr"], encoding="utf-8")

def info(path):
    with wave.open(str(path), "rb") as f:
        if f.getnchannels() < 1 or f.getnframes() < 100 or f.getframerate() < 8000:
            raise ValueError("empty/invalid WAV")
        frames=f.readframes(f.getnframes())
        if f.getsampwidth()!=2:
            raise ValueError("unexpected PCM width")
        values=struct.iter_unpack("<h",frames)
        count=0
        sumsq=0
        peak=0
        for (x,) in values:
            sumsq+=x*x
            peak=max(peak, abs(x))
            count+=1
        if not count or peak==0:
            raise ValueError("silent WAV")
        return {"duration_s": round(f.getnframes()/f.getframerate(),3),
                "sample_rate": f.getframerate(), "peak": peak,
                "rms": round(math.sqrt(sumsq/count),1), "wav_bytes": path.stat().st_size}

def page(rep):
    lookup={(a["model"],a["id"],a["mode"]):a for a in rep["samples"]}
    cells=[]
    for c in CASES:
        variants=[]
        for mode in ("raw","spoken"):
            text=c["formula"] if mode=="raw" else c["spoken"]
            model_rows=[]
            for model,_,ids in MODELS:
                if c["id"] not in ids:
                    continue
                r=lookup.get((model,c["id"],mode))
                status=r["status"] if r else "未実行"
                sound=(f'<audio controls preload="none" src="{esc(r["wav"])}"></audio>'
                       if r and r.get("wav") else "")
                meta=(f'音声 {esc(r["duration_s"])} 秒 · 処理 {esc(r["wall_s"])} 秒'
                      if r and r.get("duration_s") else "")
                loglink=(f'<a href="{esc(r["log"])}">ログ</a>' if r and r.get("log") else "")
                model_rows.append(f'<div class="model"><small>{esc(model)} — {esc(status)}'
                                  f' · {meta} {loglink}</small>{sound}</div>')
            variants.append(f'<div class="variant"><strong>{"記号そのまま" if mode=="raw" else "読みへ変換"}</strong>'
                            f'<code>{esc(text)}</code>{"".join(model_rows)}</div>')
        cells.append(f'<section class="case"><h2>{esc(c["label"])}</h2>'
                     f'<div class="equation">{esc(c["formula"])}</div>'
                     f'<div class="pair">{"".join(variants)}</div></section>')
    doc=f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <meta name="color-scheme" content="dark light">
    <title>Irodori-TTS 数式読み上げ A/B 比較</title>
    <style>
    :root{{--bg:#101825;--fg:#edf4ff;--sub:#aec0d5;--panel:#1d2b3f;--line:#405772;--link:#9bd3ff}}
    @media(prefers-color-scheme:light){{:root{{--bg:#f3f6fb;--fg:#182337;--sub:#4a5d75;--panel:#fff;--line:#c5d0e0;--link:#0757a7}}}}
    *{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,sans-serif}}
    main{{max-width:1100px;margin:auto;padding:24px 18px 80px}}a{{color:var(--link)}}
    p,small{{color:var(--sub)}}h1{{font-size:clamp(26px,5vw,42px);line-height:1.25}}
    h2{{font-size:22px;margin:0 0 8px}}.case{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:20px;margin:20px 0}}
    .equation{{font:22px/1.5 ui-monospace,monospace;word-break:break-word;margin-bottom:12px}}
    .pair{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}}
    .variant{{border:1px solid var(--line);border-radius:10px;padding:12px;min-width:0}}
    code{{display:block;white-space:pre-wrap;word-break:break-word;color:var(--fg);margin:6px 0 14px}}
    .model{{border-top:1px solid var(--line);padding:10px 0 4px}}.model small{{display:block}}
    audio{{display:block;width:100%;max-width:100%;margin-top:7px}}
    @media(max-width:650px){{.pair{{grid-template-columns:1fr}}}}
    </style></head><body><main>
    <p><a href="../">← tmp-speech</a> · speech.cpp / Irodori-TTS</p>
    <h1>数式を読ませてみる</h1>
    <p>記号をそのまま入力した音声と、数学的な日本語へ書き換えた音声を聞き比べる実験です。
    あくまで<strong>発声結果のA/Bテスト</strong>であり、数学的な正しさや自然さを自動採点したものではありません。</p>
    <p>Ubuntu 24.04 / CPU / speech.cpp v0.8.3 / seed=42 /
    MF版4ステップ（全8式）・通常版16ステップ（分数と積分のみ）。
    生成日: {esc(rep["updated_utc"])} · <a href="results.json">JSON結果</a> ·
    <a href="{esc(rep["run_url"])}">Actionsログ・Artifacts</a></p>
    {"".join(cells)}
    <p>読み換えの日本語は人手で用意しました。読み換え時に一部表現を補足・短縮しているので、
    厳密な音質比較ではありません。音声が自然かどうかは再生して判断してください。</p>
    </main></body></html>"""
    (OUT/"index.html").write_text(doc,encoding="utf-8")
    (OUT/"results.json").write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding="utf-8")
    index=ROOT/"index.html"
    if index.exists():
        html=index.read_text(encoding="utf-8")
        if 'href="math/"' not in html and "<main>" in html:
            index.write_text(html.replace("<main>",'<main><p style="border:1px solid #648ea0;border-radius:9px;padding:12px"><a href="math/">∫ Irodori 数式読み上げ A/B 比較 →</a></p>',1),encoding="utf-8")

def main():
    rep={"schema":1,"updated_utc":datetime.now(timezone.utc).isoformat(),
         "run_url":f'https://github.com/{os.getenv("GITHUB_REPOSITORY","2rwa/tmp-speech")}/actions/runs/{os.getenv("GITHUB_RUN_ID","")}',
         "threads":THREADS,"python":platform.python_version(),"cases":CASES,"models":[],
         "samples":[]}
    page(rep)
    for model,steps,ids in MODELS:
        print("Downloading",model,flush=True)
        p=timed(["speech","pull",model],1200)
        save_log(model+"-pull",p)
        rep["models"].append({"model":model,"steps":steps,"pull_exit":p["exit_code"],"pull_s":p["elapsed_s"]})
        for c in CASES:
            if c["id"] not in ids: continue
            for mode in ("raw","spoken"):
                ident=f"{model}-{c['id']}-{mode}"
                row={"id":c["id"],"model":model,"steps":steps,"mode":mode,
                     "input":c["formula"] if mode=="raw" else c["spoken"],
                     "status":"model download failed" if p["exit_code"]!=0 else "pending"}
                rep["samples"].append(row)
                if p["exit_code"]==0:
                    out=AUDIO/(ident+".wav")
                    cmd=["speech","tts",model,"--device","cpu","--threads",str(THREADS),
                         "--voice","none","--steps",str(steps),"--seed","42",
                         "-o",str(out),row["input"]]
                    r=timed(cmd,300)
                    save_log(ident,r)
                    row.update(wall_s=r["elapsed_s"],exit_code=r["exit_code"],
                               log="logs/"+ident+".log")
                    if r["exit_code"]==0 and out.exists():
                        try:
                            row.update(info(out))
                            row.update(status="ok",wav="audio/"+ident+".wav")
                        except (ValueError,OSError,wave.Error) as e:
                            row["status"]="invalid wav: "+str(e)
                    else:
                        row["status"]=r.get("error","tts failed")
                rep["updated_utc"]=datetime.now(timezone.utc).isoformat()
                page(rep)
                print(ident,row["status"],row.get("wall_s"),flush=True)
    ok=sum(a["status"]=="ok" for a in rep["samples"])
    print(f"Math experiment: {ok}/{len(rep['samples'])} valid WAVs",flush=True)
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf-8") as f:
            f.write(f'## Irodori 数式読み上げ\n\n- {ok}/{len(rep["samples"])} WAVs\n- https://2rwa.github.io/tmp-speech/math/\n')
    if not ok: raise RuntimeError("No valid audio generated")

if __name__=="__main__":
    main()
