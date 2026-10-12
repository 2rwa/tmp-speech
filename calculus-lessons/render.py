#!/usr/bin/env python3
"""Render an incremental, accessible calculus audio lesson site."""
from __future__ import annotations
from pathlib import Path
from html import escape
from datetime import datetime, timezone
import json

ROOT = Path("public")
OUT = ROOT / "calculus"
OUT.mkdir(parents=True, exist_ok=True)

def lessons():
    data = []
    for part in sorted(Path("calculus-lessons/data").glob("part*.json")):
        data.extend(json.loads(part.read_text(encoding="utf-8")))
    return data

def attr(v):
    return escape(str(v), quote=True)

def math_element(tex, display=False):
    cls = "formula" if display else "inline-math"
    return f'<span class="{cls}" data-tex="{attr(tex)}">{escape(tex)}</span>'

def audio(src):
    return f'<audio controls preload="none" src="{attr(src)}"></audio>' if src else '<span class="waiting">音声待機中</span>'

def render(report, data=None):
    data = data if data is not None else lessons()
    OUT.mkdir(parents=True, exist_ok=True)
    samples = {(s["lesson_id"], s["part"]): s for s in report.get("samples", [])}
    full = {s["lesson_id"]: s for s in report.get("combined", [])}
    cards = []
    for number, lesson in enumerate(data, start=1):
        lesson_id = lesson["id"]
        details = []
        for i, (tex, explanation) in enumerate(lesson["steps"], start=1):
            details.append(f'<li><div class="step-math">{math_element(tex)}</div>'
                           f'<p>{escape(explanation)}</p></li>')
        recordings = []
        for i, text in enumerate(lesson["narration"]):
            s = samples.get((lesson_id, i), {})
            label = ["問題", "解説・前半", "解説・後半"][i]
            time_label = f' · 音声 {s["duration_s"]}秒' if s.get("duration_s") else ""
            recordings.append(
                f'<details class="segment"><summary>{label} · {escape(s.get("status", "待機中"))}{time_label}</summary>'
                f'<p lang="ja" class="reading">{escape(text)}</p>{audio(s.get("mp3"))}</details>'
            )
        f = full.get(lesson_id, {})
        completed = f.get("status") == "ok"
        cards.append(f'''<article class="lesson" id="{attr(lesson_id)}">
          <header><span class="level">{attr(lesson["level"])} · {number:02d}</span>
          <h2>{escape(lesson["title"])}</h2></header>
          <h3>問題</h3><div class="display-math">{math_element(lesson["question_tex"], True)}</div>
          <h3>解答</h3><div class="display-math answer">{math_element(lesson["answer_tex"], True)}</div>
          <h3>解説の手順</h3><ol class="steps">{"".join(details)}</ol>
          <div class="playbox"><strong>問題から解説まで通して再生</strong>
          <small>{'完成・' + str(f.get("duration_s")) + '秒' if completed else escape(f.get("status", "音声を生成中"))}</small>
          {audio(f.get("mp3") if completed else None)}</div>
          <h3>ひらがな台本と部分音声</h3>{"".join(recordings)}
          </article>''')
    ok = sum(s.get("status") == "ok" for s in report.get("samples", []))
    total = sum(len(l["narration"]) for l in data)
    html = f'''<!doctype html><html lang="ja"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <meta name="color-scheme" content="dark light">
    <title>微分から置換積分まで | Irodori-TTS 音声教材</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
    <style>
    :root{{--bg:#101822;--panel:#1c293b;--text:#f1f6fc;--muted:#b0bfd1;--line:#43566d;--accent:#87ceff}}
    @media(prefers-color-scheme:light){{:root{{--bg:#f3f6fa;--panel:white;--text:#172334;--muted:#4f6073;--line:#bdcbd8;--accent:#0757a5}}}}
    *{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--bg);color:var(--text);
      font:16px/1.65 system-ui,-apple-system,'Noto Sans JP',sans-serif}}
    main{{max-width:990px;margin:auto;padding:24px 18px 80px}}
    h1{{font-size:clamp(27px,5vw,43px);line-height:1.27;margin:14px 0}}
    h2{{font-size:23px;margin:8px 0 16px}}h3{{font-size:17px;margin:22px 0 8px}}
    p,small{{color:var(--muted)}}a{{color:var(--accent)}}
    .intro{{max-width:750px}}.index{{display:flex;flex-wrap:wrap;gap:8px;padding:12px 0 20px}}
    .index a{{border:1px solid var(--line);border-radius:100px;padding:5px 12px;text-decoration:none}}
    .lesson{{background:var(--panel);border:1px solid var(--line);border-radius:16px;
       margin:22px 0;padding:clamp(14px,3vw,26px)}}
    .level{{font-size:13px;color:var(--muted);letter-spacing:.05em}}
    .display-math{{overflow-x:auto;padding:16px 8px;border:1px solid var(--line);border-radius:9px}}
    .formula{{display:inline-block;font-size:19px;min-width:max-content}}
    .answer{{border-left:4px solid var(--accent)}}
    .steps{{padding-left:25px}}.steps li{{padding:10px 0;border-bottom:1px solid var(--line)}}
    .steps li:last-child{{border-bottom:0}}.steps p{{margin:5px 0}}
    .step-math{{overflow-x:auto}}.inline-math{{font-size:17px}}
    .playbox{{background:rgba(130,180,220,.09);padding:14px;border-radius:12px;
      border:1px solid var(--line);margin-top:22px}}
    .playbox strong,.playbox small{{display:block}}
    audio{{width:100%;max-width:600px;display:block;margin:10px 0}}
    .segment{{border:1px solid var(--line);border-radius:9px;margin:7px 0;padding:10px 14px}}
    summary{{cursor:pointer;font-weight:600}}.reading{{line-height:1.9;overflow-wrap:anywhere}}
    .waiting{{color:var(--muted);display:block;margin-top:8px}}
    </style></head><body><main>
    <p><a href="../">← tmp-speech トップ</a> / <a href="../math/">数式単体の読み上げ比較</a></p>
    <h1>微分から置換積分まで<br>聴いて学ぶ問題と解説</h1>
    <p class="intro">基本的な微分から置換積分まで全{len(data)}問。数式・計算過程を表示し、
    問題と解説を<strong>ひらがなの音声台本</strong>にして Irodori-TTS で合成します。
    各章の連続音声と、問題・解説の分割音声を聴き比べられます。</p>
    <p>合成: speech.cpp v0.8.3 / irodori-tts-mf / CPU 4ステップ / seed 42 /
    {ok}/{total}区間成功 · 更新 {attr(report.get("updated_utc","未実行"))} ·
    <a href="results.json">計測JSON</a> · <a href="{attr(report.get("run_url","https://github.com/2rwa/tmp-speech/actions"))}">Actions実行ログ</a></p>
    <nav class="index" aria-label="問題一覧">{''.join(f'<a href="#{attr(l["id"])}">{i}. {escape(l["title"])}</a>' for i,l in enumerate(data,1))}</nav>
    {''.join(cards)}
    <p>数式の読みは学習者が理解しやすいよう手動で作成しました。ひらがな表記と音声の対応は、
    誤読・不自然な区切りを含む可能性があるため、音声品質の自動評価は行っていません。
    記号の解釈ではなく、数式の説明を日本語で読み上げる実験です。</p></main>
    <script>window.addEventListener('load',()=>{{
      document.querySelectorAll('[data-tex]').forEach(el=>{{
        if(!window.katex)return;
        try{{window.katex.render(el.dataset.tex,el,{{throwOnError:false,displayMode:el.classList.contains('formula')}})}}
        catch(e){{console.warn('Math rendering',e)}} 
      }});
    }});</script></body></html>'''
    (OUT/"index.html").write_text(html, encoding="utf-8")
    (OUT/"results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    home = ROOT/"index.html"
    if home.is_file():
        content = home.read_text(encoding="utf-8")
        if 'href="calculus/"' not in content and "<main>" in content:
            nav = '<main><p style="border:1px solid #527ca7;border-radius:9px;padding:12px"><a href="calculus/">∫ 微分・積分の読み上げ音声教材 →</a></p>'
            home.write_text(content.replace("<main>",nav,1),encoding="utf-8")
