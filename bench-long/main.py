"""Aozora Bunko full-story Irodori CPU + process memory benchmark."""
from html.parser import HTMLParser
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, urlopen
import hashlib, html, json, os, platform, re, shutil, statistics, subprocess, time, wave

PUB=Path("public")
OUT=PUB/"long"
URL="https://www.aozora.gr.jp/cards/000879/files/92_14545.html"
CARD="https://www.aozora.gr.jp/cards/000879/card92.html"
MODELS=[("irodori-tts-mf",4),("irodori-tts",16)]

class RubyReader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active=False; self.depth=0; self.seen=False
        self.parts=[]; self.base=None; self.reading=None
        self.rt=False; self.rp=False; self.unknown=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="div":
            if not self.active and "main_text" in a.get("class","").split():
                self.active=True; self.depth=1; self.seen=True; return
            if self.active: self.depth+=1
        if not self.active: return
        if tag=="ruby": self.base=[]; self.reading=[]
        if tag=="rt": self.rt=True
        if tag=="rp": self.rp=True
        if tag=="br": self.parts.append("\n")
        if tag=="img":
            if "特のへん" in a.get("alt","") or "犍" in a.get("alt",""): self.parts.append("犍")
            else: self.unknown.append(a.get("alt",""))
    def handle_endtag(self,tag):
        if not self.active: return
        if tag=="rt": self.rt=False
        if tag=="rp": self.rp=False
        if tag=="ruby" and self.base is not None:
            self.parts.append("".join(self.reading).strip() or "".join(self.base))
            self.base=self.reading=None
        if tag=="div":
            self.depth-=1; self.parts.append("\n")
            if self.depth==0: self.active=False
        if tag in ("h4","h3","p"): self.parts.append("\n")
    def handle_data(self,s):
        if not self.active or self.rp: return
        if self.base is not None: (self.reading if self.rt else self.base).append(s)
        else: self.parts.append(s)

def prepare_text():
    req=Request(URL,headers={"User-Agent":"tmp-speech-benchmark/1.0"})
    with urlopen(req,timeout=90) as res: raw=res.read()
    reader=RubyReader(); reader.feed(raw.decode("cp932"))
    if not reader.seen or reader.unknown: raise ValueError("body or gaiji error: "+repr(reader.unknown))
    lines=[]
    for s in "".join(reader.parts).splitlines():
        s=re.sub(r"[\u3000\t ]+","",s.strip())
        if not s: continue
        if s in ("一","二","三"): s={"一":"第一章。","二":"第二章。","三":"第三章。"}[s]
        if re.fullmatch(r"[（(]大正.+?[）)]",s): continue
        lines.append(s)
    text="".join(lines)
    if not (2000<len(text)<6500) or "ある日の事でございます" not in text or "極楽ももう" not in text:
        raise ValueError("Unexpected text length or contents: "+str(len(text)))
    (OUT/"normalized.txt").write_text(text+"\n",encoding="utf8")
    meta={"title":"蜘蛛の糸","author":"芥川龍之介","card":CARD,"html":URL,
          "source_sha256":hashlib.sha256(raw).hexdigest(),
          "normalized_sha256":hashlib.sha256(text.encode()).hexdigest(),
          "characters":len(text),"ruby_handling":"ルビは読みで置換、外字は犍へ復元"}
    (OUT/"source.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf8")
    return meta

def preserve_short():
    """Pages replaces the entire site, so copy the existing short benchmark first."""
    names=["index.html","results.json"]
    for m,_ in MODELS:
        for label in ("short","medium"):
            names.extend([f"audio/{m}-{label}.wav",f"logs/{m}-{label}.log"])
        names.append(f"logs/{m}-pull.log")
    ok=True
    for name in names:
        try:
            with urlopen("https://2rwa.github.io/tmp-speech/"+name,timeout=30) as f: data=f.read()
            dst=PUB/name; dst.parent.mkdir(parents=True,exist_ok=True); dst.write_bytes(data)
        except Exception as e:
            print("Previous Pages fetch:",name,repr(e),flush=True); ok=False
    index=PUB/"index.html"
    if index.exists():
        content=index.read_text(encoding="utf8")
        content=content.replace("<main>",'<main><p style="border:1px solid #557baf;border-radius:9px;padding:12px"><a href="long/">『蜘蛛の糸』全文・長尺メモリベンチマーク →</a></p>',1)
    else:
        content='<!doctype html><html lang="ja"><meta charset="utf-8"><title>tmp-speech</title><a href="long/">蜘蛛の糸・長尺ベンチマーク</a></html>'
    index.write_text(content,encoding="utf8")
    return ok

def threads():
    n=len(os.sched_getaffinity(0))
    try:
        quota,period=Path("/sys/fs/cgroup/cpu.max").read_text().split()[:2]
        if quota!="max": n=min(n,max(1,int(quota)//int(period)))
    except (OSError,ValueError): pass
    return max(1,min(4,n))

def rss(pid,t0):
    try:
        status=Path(f"/proc/{pid}/status").read_text()
        def get(name):
            m=re.search(rf"^{name}:\s*(\d+) kB$",status,re.M)
            return round(int(m.group(1))/1024,2) if m else None
        return {"t_s":round(time.monotonic()-t0,2),"rss_mib":get("VmRSS"),
                "hwm_mib":get("VmHWM"),"vms_mib":get("VmSize")}
    except OSError: return None

def process(cmd,log,stdin=None,timeout=10500):
    t0=time.monotonic(); samples=[]; limit=False
    with log.open("w",encoding="utf8") as f:
        with subprocess.Popen(cmd,stdin=stdin,stdout=f,stderr=subprocess.STDOUT) as p:
            while p.poll() is None:
                v=rss(p.pid,t0)
                if v: samples.append(v)
                if time.monotonic()-t0>timeout:
                    limit=True; p.terminate()
                    try: p.wait(timeout=10)
                    except subprocess.TimeoutExpired: p.kill()
                    break
                time.sleep(1)
            return {"exit":p.wait(),"timeout":limit,
                    "seconds":round(time.monotonic()-t0,3),"memory_samples":samples}

def mem_stats(samples):
    rss_vals=sorted(x["rss_mib"] for x in samples if x.get("rss_mib") is not None)
    if not rss_vals: return {}
    hwm=[x["hwm_mib"] for x in samples if x.get("hwm_mib") is not None]
    return {"min_mib":rss_vals[0],"mean_mib":round(statistics.mean(rss_vals),2),
            "p95_mib":rss_vals[min(len(rss_vals)-1,int(len(rss_vals)*.95))],
            "peak_mib":max(hwm or rss_vals),"last_mib":rss_vals[-1],
            "samples":len(rss_vals)}

def esc(s): return html.escape(str(s),quote=True)
def fmt(v,suffix=""): return "—" if v is None else esc(v)+suffix

def graph(series):
    pairs=[(x["t_s"],x["rss_mib"]) for x in series if x.get("rss_mib") is not None]
    if not pairs: return "<p>計測データなし</p>"
    xmax=max(1,pairs[-1][0]); ymax=max(1,max(y for _,y in pairs)*1.1)
    samples=pairs[::max(1,len(pairs)//900)]
    if samples[-1]!=pairs[-1]: samples.append(pairs[-1])
    coords=" ".join(f"{40+x/xmax*920:.1f},{185-y/ymax*165:.1f}" for x,y in samples)
    return (f'<svg role="img" aria-label="RSSの時間推移" viewBox="0 0 1000 220" style="width:100%;height:auto">'
            f'<path d="M40 20V185H970" fill="none" stroke="#647b9a"/>'
            f'<polyline fill="none" stroke="#5ccaff" stroke-width="2.3" points="{coords}"/>'
            f'<text x="43" y="14" fill="currentColor">{ymax:.0f} MiB</text>'
            f'<text x="44" y="211" fill="currentColor">0</text>'
            f'<text x="860" y="211" fill="currentColor">{xmax/60:.1f} min</text></svg>')

def page(report):
    cards=[]
    for m in report.get("models",[]):
        s=m.get("stats",{})
        metrics=[("合成時間",fmt(m.get("seconds")," 秒")),
                 ("完成音声",fmt(m.get("audio_seconds")," 秒")),
                 ("Wall RTF",fmt(m.get("wall_rtf"))),
                 ("最大RSS",fmt(s.get("peak_mib")," MiB")),
                 ("平均RSS",fmt(s.get("mean_mib")," MiB")),
                 ("p95 RSS",fmt(s.get("p95_mib")," MiB"))]
        grid="".join(f"<div><small>{esc(k)}</small><strong>{v}</strong></div>" for k,v in metrics)
        audio=f'<audio controls preload="none" src="{esc(m["mp3"])}"></audio>' if m.get("mp3") else ""
        cards.append(f'''<section class="box"><h2>{esc(m["name"])} ({m["steps"]} steps)</h2>
        <p>状態: {esc(m.get("status","queued"))} /
        <a href="{esc(m["name"])}.log">ログ</a></p>
        <div class="metrics">{grid}</div>{audio}
        <p>RSSを約1秒間隔で測定: {len(m.get("memory_samples",[]))}件</p>
        {graph(m.get("memory_samples",[]))}</section>''')
    source=report.get("source") or {}
    content=f'''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <meta name="color-scheme" content="dark light"><title>蜘蛛の糸・長尺TTS・メモリ</title>
    <style>:root{{--bg:#101925;--panel:#1c2a3c;--fg:#eef4ff;--muted:#b0c2d6;--link:#8ccfff}}
    @media(prefers-color-scheme:light){{:root{{--bg:#f4f8fb;--panel:white;--fg:#152233;--muted:#58677b;--link:#1260a8}}}}
    *{{box-sizing:border-box}}body{{background:var(--bg);color:var(--fg);font:16px/1.7 system-ui;margin:0}}
    main{{max-width:1050px;margin:auto;padding:28px 20px 90px}}
    h1{{font-size:clamp(27px,5vw,44px);line-height:1.25}}a{{color:var(--link)}}p,small{{color:var(--muted)}}
    .box{{background:var(--panel);border:1px solid #455b75;padding:20px;border-radius:15px;margin:22px 0}}
    .metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:12px}}
    .metrics div{{border:1px solid #46607c;border-radius:9px;padding:12px}}
    .metrics small,.metrics strong{{display:block}}.metrics strong{{font-size:23px}}audio{{max-width:100%;width:500px;margin:18px 0}}</style>
    <main><p><a href="../">← 短文ベンチマーク</a></p><h1>『蜘蛛の糸』全文の長尺合成</h1>
    <p>speech.cpp · Irodori-TTS · CPUメモリ使用量と合成時間</p>
    <section class="box"><h2>測定条件</h2>
    <p>青空文庫『蜘蛛の糸』（芥川龍之介）をルビを読みへ変換して全文合成。
    <a href="{CARD}">出典</a> / <a href="normalized.txt">音声入力テキスト</a> /
    <a href="source.json">取得元とSHA256</a>。文字数: {fmt(source.get("characters"))}</p>
    <p>CPU: {esc(report.get("cpu","—"))}; スレッド: {esc(report.get("threads","—"))};
    OS: {esc(report.get("os","—"))}; 生成 (UTC): {esc(report.get("updated_utc","—"))}</p>
    <p>MF版4ステップ／通常版16ステップ。各モデルは独立プロセス・seed=42。
    合成時間はモデル読み込みを含み、初回ダウンロードやMP3への変換は除外。
    Wall RTF = 合成時間 ÷ 完成音声の長さ。
    RSSは/proc/pid/statusのVmRSS、p95・平均・最大値を記録（GPUメモリではありません）。</p></section>
    {''.join(cards)}
    <section class="box"><h2>生データ・クレジット</h2>
    <p><a href="results.json">全メモリ時系列と統計（JSON）</a> /
    <a href="{esc(report.get("run_url","https://github.com/2rwa/tmp-speech/actions"))}">GitHub ActionsとArtifacts</a> /
    <a href="https://github.com/2rwa/tmp-speech">GitHubソース</a></p>
    <p>底本『芥川龍之介全集2』ちくま文庫。入力：野口英司・平山誠、校正：もりみつじゅんじ。
    著作権保護期間満了。音声は機械生成による研究用です。</p></section></main></html>'''
    (OUT/"index.html").write_text(content,encoding="utf8")
    (OUT/"results.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    preserved=preserve_short()
    try: cpu=next(line.split(":",1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines() if line.startswith("model name"))
    except (OSError,StopIteration): cpu=platform.processor() or "unknown"
    report={"updated_utc":datetime.now(timezone.utc).isoformat(),"cpu":cpu,
            "threads":threads(),"os":platform.platform(),"short_preserved":preserved,
            "run_url":f'https://github.com/{os.getenv("GITHUB_REPOSITORY","2rwa/tmp-speech")}/actions/runs/{os.getenv("GITHUB_RUN_ID","")}',
            "models":[]}
    try: report["source"]=prepare_text()
    except Exception as e:
        report["source_error"]=repr(e); page(report); raise
    page(report)
    for name,steps in MODELS:
        row={"name":name,"steps":steps,"status":"downloading"}
        report["models"].append(row)
        print(f"BEGIN {name} {datetime.now(timezone.utc)}",flush=True)
        pull=process(["speech","pull",name],OUT/(name+"-pull.log"),timeout=1200)
        row["download_seconds"]=pull["seconds"]
        row["download_exit"]=pull["exit"]
        if pull["exit"]!=0:
            row["status"]="download_failed"; page(report); continue
        wav=OUT/(name+".wav")
        with (OUT/"normalized.txt").open(encoding="utf8") as input_file:
            row.update(process(["speech","tts",name,"--device","cpu","--threads",str(report["threads"]),
                                "--voice","none","--steps",str(steps),"--seed","42",
                                "-o",str(wav)],OUT/(name+".log"),stdin=input_file,timeout=10500))
        row["stats"]=mem_stats(row["memory_samples"])
        row["status"]="ok" if row["exit"]==0 and not row["timeout"] else "failed_or_timed_out"
        if row["status"]=="ok":
            try:
                with wave.open(str(wav),"rb") as f:
                    row["audio_seconds"]=round(f.getnframes()/f.getframerate(),3)
                    row["sample_rate_hz"]=f.getframerate()
                if row["audio_seconds"]<30: raise ValueError("Too little audio")
                row["wall_rtf"]=round(row["seconds"]/row["audio_seconds"],3)
                mp3=OUT/(name+".mp3")
                conv=subprocess.run(["ffmpeg","-nostdin","-hide_banner","-loglevel","error","-y",
                                     "-i",str(wav),"-ac","1","-c:a","libmp3lame","-b:a","80k",
                                     str(mp3)],capture_output=True,text=True,timeout=600)
                if conv.returncode!=0 or not mp3.is_file(): raise ValueError(conv.stderr[-500:])
                row["mp3"]=mp3.name; row["mp3_bytes"]=mp3.stat().st_size
            except Exception as e: row["status"]="audio_error: "+repr(e)
        wav.unlink(missing_ok=True)
        report["updated_utc"]=datetime.now(timezone.utc).isoformat()
        page(report)
        print("FINISH",name,row["status"],row.get("seconds"),row.get("stats"),flush=True)
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf8") as f:
            f.write("## Aozora Bunko / Kumono Ito CPU long benchmark\n\n")
            for m in report["models"]:
                f.write(f'- {m["name"]}: {m["status"]}; wall {m.get("seconds")}s; peakRSS {m.get("stats",{}).get("peak_mib")} MiB\n')
            f.write("\nhttps://2rwa.github.io/tmp-speech/long/\n")
    if len(report["models"])!=2 or any(m["status"]!="ok" for m in report["models"]):
        raise RuntimeError("One or more long benchmarks failed; partial report saved.")

if __name__=="__main__":
    main()
