#!/usr/bin/env python3
"""CPU-only speech.cpp benchmark: preserve failures, real WAVs, and raw CLI logs."""
import datetime as dt
import html
import json
import os
import pathlib
import platform
import re
import shutil
import subprocess
import time
import wave

OUT = pathlib.Path("public")
(OUT / "audio").mkdir(parents=True, exist_ok=True)
(OUT / "logs").mkdir(parents=True, exist_ok=True)
MODELS = [("irodori-tts-mf", 4), ("irodori-tts", 16)]
TEXTS = [
    ("short", "こんにちは。"),
    ("medium", "今日は音声合成の速度を計測します。"),
]

def cpu_threads():
    n = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count() or 2
    try:
        q, p = pathlib.Path("/sys/fs/cgroup/cpu.max").read_text().split()[:2]
        if q != "max":
            n = min(n, max(1, int(q) // int(p)))
    except (OSError, ValueError):
        pass
    return max(1, min(n, 4))

def command(args, timeout):
    start = time.perf_counter()
    try:
        p = subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=False)
        return dict(exit_code=p.returncode, stdout=p.stdout[-12000:],
                    stderr=p.stderr[-20000:], elapsed_s=round(time.perf_counter() - start, 3))
    except subprocess.TimeoutExpired as e:
        def decode(x):
            return x.decode("utf-8", "replace") if isinstance(x, bytes) else x or ""
        return dict(exit_code=None, stdout=decode(e.stdout)[-12000:],
                    stderr=decode(e.stderr)[-20000:],
                    elapsed_s=round(time.perf_counter() - start, 3), error="timeout")
    except OSError as e:
        return dict(exit_code=None, stdout="", stderr=str(e), elapsed_s=0, error="exec failed")

def log(name, run):
    (OUT / "logs" / (name + ".log")).write_text(
        f"exit_code: {run['exit_code']}\nwall_seconds: {run['elapsed_s']}\n"
        + "STDOUT\n" + run["stdout"] + "\nSTDERR\n" + run["stderr"],
        encoding="utf-8")

def wav_info(path):
    with wave.open(str(path), "rb") as f:
        frames = f.getnframes()
        rate = f.getframerate()
        return dict(seconds=round(frames / rate, 3), rate_hz=rate,
                    channels=f.getnchannels(), bytes=path.stat().st_size)

def reported(stderr):
    """Best-effort CLI timing extraction; raw logs are authoritative."""
    d = {}
    patterns = [
        ("first_audio_s", r"(?:first audio|time to first audio)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*s"),
        ("reported_rtf", r"(?:real[- ]time factor|\bRTF\b)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)"),
    ]
    for name, pat in patterns:
        m = re.search(pat, stderr, re.I)
        if m:
            d[name] = float(m.group(1))
    return d

def card_value(value, suffix=""):
    return "—" if value is None else html.escape(str(value)) + suffix

def render(report):
    cards = []
    for m in report["models"]:
        samples = []
        for s in m["samples"]:
            audio = s.get("wav")
            player = ('<audio controls preload="none" src="' + html.escape(audio, quote=True) + '"></audio>'
                      if audio else "")
            samples.append(f"""<tr><td>{html.escape(s['id'])}</td>
              <td>{html.escape(s['status'])}</td>
              <td>{card_value(s.get('wav_seconds'),' s')}</td>
              <td>{card_value(s.get('wall_s'),' s')}</td>
              <td>{card_value(s.get('wall_rtf'))}</td>
              <td>{card_value(s.get('reported_rtf'))}</td>
              <td>{card_value(s.get('first_audio_s'),' s')}</td>
              <td>{player}</td></tr>""")
        cards.append(f"""<section class="panel"><div class="heading"><h2>{html.escape(m['name'])}</h2>
          <span class="tag">{m['steps']} steps</span></div>
          <p>モデル取得: {html.escape(m['pull']['status'])}
          （{card_value(m['pull'].get('seconds'))} 秒）</p>
          <div class="scroll"><table><thead><tr><th>入力</th><th>状態</th>
          <th>音声長</th><th>実行時間</th><th>Wall RTF</th>
          <th>CLI RTF</th><th>First audio</th><th>試聴</th></tr></thead>
          <tbody>{''.join(samples)}</tbody></table></div></section>""")
    date = html.escape(report["generated_utc"])
    run_url = html.escape(report["run_url"], quote=True)
    body = f"""<!doctype html><html lang="ja"><head>
    <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <meta name="color-scheme" content="dark light">
    <title>speech.cpp CPU Benchmark | tmp-speech</title>
    <style>
    :root{{--bg:#101722;--panel:#1a2534;--muted:#aab8cb;--text:#f5f7fb;--link:#87c7ff}}
    *{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);
    font:16px/1.6 system-ui,-apple-system,sans-serif}}
    main{{max-width:1080px;margin:auto;padding:32px 20px 90px}}
    h1{{font-size:clamp(26px,5vw,44px);line-height:1.2}}h2{{margin:0;font-size:21px}}
    p,li{{color:var(--muted)}}a{{color:var(--link)}}small{{color:var(--muted)}}
    .eyebrow{{letter-spacing:.1em;text-transform:uppercase;color:#a8c6fa;font-size:12px}}
    .panel{{background:var(--panel);border:1px solid #36455a;border-radius:16px;
    padding:22px;margin-top:20px}}
    .heading{{display:flex;align-items:center;gap:14px;flex-wrap:wrap}}
    .tag{{border:1px solid #52759e;border-radius:99px;padding:3px 10px;font-size:12px}}
    .scroll{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;margin-top:14px;
    font-size:14px;white-space:nowrap}}th,td{{padding:12px 14px;border-bottom:1px solid #38465a;
    text-align:left}}th{{color:#a8c6fa}}audio{{width:170px;height:36px}}
    code{{color:#b1e5e8;overflow-wrap:anywhere}}@media(prefers-color-scheme:light){{
    :root{{--bg:#f4f7fa;--panel:white;--muted:#455568;--text:#182235;--link:#075db1}}}}
    </style></head><body><main><div class="eyebrow">2rwa / tmp-speech</div>
    <h1>speech.cpp — Irodori-TTS<br>CPUベンチマーク</h1>
    <p>GitHub Actions・Ubuntu 24.04 / x86-64 / CPUのみ。実行日 (UTC): {date}</p>
    <div class="panel"><h2>計測条件</h2>
      <p>speech.cpp: <code>{html.escape(report['speech_version'])}</code> /
      Python: {html.escape(report['python_version'])} /
      CPU: {html.escape(report['cpu'])} /
      threads: {report['threads']} /
      OS: {html.escape(report['os'])}</p>
      <p>各モデルで2つの日本語文を、同じシードで順番に合成。
      各試行はモデル読み込みを含む<strong>独立したCLIプロセス</strong>です。
      通常版は16ステップ、MF版は4ステップ。音声品質の優劣は自動判定していません。</p>
      <p><strong>Wall RTF</strong> = コマンド全体の時間 ÷ 生成音声の長さ（モデル読み込みを含む）。
      <strong>CLI RTF</strong>と<strong>First audio</strong>はspeech.cppのログから抽出できた場合のみ表示。
      空欄は未計測・解析不能であり、0秒を意味しません。</p>
      <p>初回ダウンロード時間は合成時間と別計測。共有CPUの負荷で値は変動します。</p>
    </div>
    {''.join(cards)}
    <div class="panel"><h2>再現性と生データ</h2>
      <p>失敗やタイムアウトも隠さず表示します。<a href="results.json">測定JSON</a> /
      <a href="{run_url}">GitHub Actions実行ログとArtifacts</a> /
      <a href="https://github.com/2rwa/tmp-speech">ソース</a> /
      <a href="https://github.com/nyosegawa/speech.cpp">speech.cpp公式</a></p>
      <small>このページはCIの測定結果から自動生成されます。GPUやM1 Macのベンチマークではありません。</small>
    </div></main></body></html>"""
    (OUT / "index.html").write_text(body, encoding="utf-8")

def main():
    threads = cpu_threads()
    try:
        cpu = next((line.split(":", 1)[1].strip() for line in
                   pathlib.Path("/proc/cpuinfo").read_text().splitlines()
                   if line.startswith("model name")), platform.processor())
    except OSError:
        cpu = platform.processor() or "unknown"
    info = command(["speech", "--version"], 20)
    report = {
        "schema": 1,
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "run_url": f"https://github.com/{os.getenv('GITHUB_REPOSITORY','2rwa/tmp-speech')}/actions/runs/{os.getenv('GITHUB_RUN_ID','')}",
        "speech_version": (info["stdout"] + info["stderr"]).strip(),
        "release_requested": os.getenv("SPEECH_RELEASE", "unspecified"),
        "os": platform.platform(),
        "cpu": cpu,
        "threads": threads,
        "python_version": platform.python_version(),
        "models": [],
    }
    for name, steps in MODELS:
        m = {"name": name, "steps": steps, "samples": []}
        report["models"].append(m)
        pull = command(["speech", "pull", name], 900)
        log(name + "-pull", pull)
        m["pull"] = {"status": "ok" if pull["exit_code"] == 0 else pull.get("error","failed"),
                     "seconds": pull["elapsed_s"], "exit_code": pull["exit_code"]}
        for ident, phrase in TEXTS:
            s = {"id": ident, "text": phrase, "status": "not run"}
            m["samples"].append(s)
            if pull["exit_code"] != 0:
                s["status"] = "model download failed"
                continue
            wav = OUT / "audio" / f"{name}-{ident}.wav"
            args = ["speech", "tts", name, "--device", "cpu", "--threads", str(threads),
                    "--voice", "none", "--steps", str(steps),
                    "--seed", "42", "-o", str(wav), phrase]
            result = command(args, 600)
            log(name + "-" + ident, result)
            s["wall_s"] = result["elapsed_s"]
            s["exit_code"] = result["exit_code"]
            s.update(reported(result["stderr"]))
            if result["exit_code"] != 0:
                s["status"] = result.get("error", "tts failed")
            else:
                try:
                    w = wav_info(wav)
                    if w["seconds"] <= 0.05:
                        raise ValueError("empty audio")
                    s.update(wav_seconds=w["seconds"], sample_rate_hz=w["rate_hz"],
                             bytes=w["bytes"], wav=str(wav.relative_to(OUT)),
                             wall_rtf=round(s["wall_s"] / w["seconds"], 3),
                             status="ok")
                except (ValueError, OSError, wave.Error) as e:
                    s["status"] = "invalid wav: " + str(e)
            print(f"{name} {ident}: {s['status']}, wall {s['wall_s']}s", flush=True)
        report["generated_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        (OUT / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        render(report)
    successes = sum(s["status"] == "ok" for m in report["models"] for s in m["samples"])
    summary = (f"### speech.cpp Irodori-TTS CPU benchmark\n\n"
               f"- Successful samples: {successes}/4\n"
               f"- Results: https://2rwa.github.io/tmp-speech/\n"
               f"- CPU: {cpu}; threads: {threads}\n\n"
               f"See results.json and uploaded logs.\n")
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(summary)
    print(summary, flush=True)
    # Failures remain in published structured results; deployment should still publish diagnostics.

if __name__ == "__main__":
    main()
