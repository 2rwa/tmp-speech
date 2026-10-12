#!/usr/bin/env python3
"""Synthesize narrated calculus lessons on GitHub Actions CPU."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json
import math
import os
import subprocess
import time
import wave
from render import OUT, lessons, render

DATA = lessons()
MODEL = "irodori-tts-mf"
STEPS = 4
AUDIO = OUT/"audio"
LOGS = OUT/"logs"
TEMP = OUT/"tmp-wav"
for d in (AUDIO, LOGS, TEMP):
    d.mkdir(parents=True, exist_ok=True)

def threads():
    cpu = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else (os.cpu_count() or 2)
    try:
        quota, period = Path("/sys/fs/cgroup/cpu.max").read_text().split()[:2]
        if quota != "max":
            cpu = min(cpu, max(1, math.ceil(int(quota)/int(period))))
    except (ValueError, OSError, IndexError):
        pass
    return max(1, min(4, cpu))

THREADS = threads()

def execute(command, name, timeout):
    began = time.monotonic()
    logpath = LOGS/(name+".log")
    try:
        with logpath.open("w", encoding="utf-8") as f:
            f.write("COMMAND: " + repr(command) + "\n")
            f.flush()
            p = subprocess.run(command, stdin=subprocess.DEVNULL,
                               stdout=f, stderr=subprocess.STDOUT,
                               timeout=timeout, check=False)
        result = {"exit_code":p.returncode,"elapsed_s":round(time.monotonic()-began,3),
                  "log":"logs/"+name+".log"}
    except subprocess.TimeoutExpired:
        result = {"exit_code":None,"elapsed_s":round(time.monotonic()-began,3),
                  "log":"logs/"+name+".log","error":"timeout"}
    except OSError as exc:
        result = {"exit_code":None,"elapsed_s":round(time.monotonic()-began,3),
                  "log":"logs/"+name+".log","error":str(exc)}
    return result

def validate_wav(path):
    with wave.open(str(path),"rb") as f:
        if f.getnframes()<200 or f.getframerate()<8000 or f.getsampwidth()!=2:
            raise ValueError("unexpected or empty audio")
        nframes=f.getnframes()
        rate=f.getframerate()
        channels=f.getnchannels()
        pcm=f.readframes(nframes)
        if not pcm or not any(pcm):
            raise ValueError("silent PCM")
        return {"duration_s":round(nframes/rate,3),"sample_rate":rate,
                "channels":channels,"sample_width":2,"frames":nframes}

def mp3(wav, output, name):
    result=execute(["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
                    "-i",str(wav),"-ac","1","-codec:a","libmp3lame",
                    "-b:a","64k",str(output)],name,120)
    if result["exit_code"]!=0 or not output.is_file() or output.stat().st_size<512:
        raise RuntimeError(f"MP3 conversion failed: {result}")
    return result

def combine(chunks, target):
    first=validate_wav(chunks[0])
    with wave.open(str(target),"wb") as writer:
        writer.setnchannels(first["channels"])
        writer.setsampwidth(first["sample_width"])
        writer.setframerate(first["sample_rate"])
        for i, path in enumerate(chunks):
            info=validate_wav(path)
            if info["sample_rate"]!=first["sample_rate"] or info["channels"]!=first["channels"]:
                raise ValueError("mismatched PCM format between sections")
            if i:
                pause=round(first["sample_rate"]*.45)
                writer.writeframes(b"\x00"*pause*first["channels"]*first["sample_width"])
            with wave.open(str(path),"rb") as reader:
                while True:
                    fragment=reader.readframes(32768)
                    if not fragment:
                        break
                    writer.writeframes(fragment)
    return validate_wav(target)

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def main():
    report={"schema":1,"updated_utc":now(),"model":MODEL,"steps":STEPS,
            "threads":THREADS,"samples":[],"combined":[],
            "run_url":f'https://github.com/{os.getenv("GITHUB_REPOSITORY","2rwa/tmp-speech")}/actions/runs/{os.getenv("GITHUB_RUN_ID","")}'}
    render(report,DATA)
    pulled=execute(["speech","pull",MODEL],"model-pull",1200)
    report["pull"]=pulled
    print("MODEL",pulled,flush=True)
    for lesson in DATA:
        chapter=lesson["id"]
        chunks=[]
        for index,text in enumerate(lesson["narration"]):
            name=f"{chapter}-section-{index+1}"
            output=TEMP/(name+".wav")
            record={"lesson_id":chapter,"part":index,"name":name,
                    "text":text,"status":"pending"}
            report["samples"].append(record)
            if pulled["exit_code"]!=0:
                record["status"]="model download failed"
            else:
                command=["speech","tts",MODEL,"--device","cpu","--threads",str(THREADS),
                         "--voice","none","--steps",str(STEPS),"--seed","42",
                         "-o",str(output),text]
                tts=execute(command,name,300)
                record.update({"wall_s":tts["elapsed_s"],
                               "log":tts["log"],"exit_code":tts["exit_code"]})
                if tts["exit_code"]!=0:
                    record["status"]=tts.get("error","tts failed")
                else:
                    try:
                        wavstats=validate_wav(output)
                        compressed=AUDIO/(name+".mp3")
                        mp3(output,compressed,name+"-encode")
                        record.update(wavstats)
                        record.update({"mp3":"audio/"+compressed.name,
                                       "mp3_bytes":compressed.stat().st_size,
                                       "status":"ok"})
                        chunks.append(output)
                    except (ValueError, OSError, RuntimeError, wave.Error) as exc:
                        record["status"]="invalid audio: "+repr(exc)
            print("SECTION",name,record["status"],record.get("wall_s"),flush=True)
            report["updated_utc"]=now()
            render(report,DATA)
        combined={"lesson_id":chapter,"status":"incomplete"}
        report["combined"].append(combined)
        if len(chunks)==len(lesson["narration"]):
            try:
                wav=TEMP/(chapter+"-full.wav")
                stats=combine(chunks,wav)
                output=AUDIO/(chapter+"-full.mp3")
                mp3(wav,output,chapter+"-full-encode")
                combined.update(stats)
                combined.update({"status":"ok","mp3":"audio/"+output.name,
                                 "bytes":output.stat().st_size})
                wav.unlink(missing_ok=True)
            except (ValueError,OSError,RuntimeError,wave.Error) as exc:
                combined["status"]="combine failed: "+repr(exc)
        for chunk in chunks:
            chunk.unlink(missing_ok=True)
        print("CHAPTER",chapter,combined["status"],flush=True)
        report["updated_utc"]=now()
        render(report,DATA)
    ok=sum(s["status"]=="ok" for s in report["samples"])
    okfull=sum(s["status"]=="ok" for s in report["combined"])
    total=sum(len(l["narration"]) for l in DATA)
    print(f"CALCULUS FINISHED: {ok}/{total} sections and {okfull}/{len(DATA)} lessons",flush=True)
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf-8") as f:
            f.write(f'### Irodori-TTS calculus lessons\n\n'
                    f'- Sections: {ok}/{total}\n- Combined lessons: {okfull}/{len(DATA)}\n'
                    f'- Published: https://2rwa.github.io/tmp-speech/calculus/\n')
    if ok!=total or okfull!=len(DATA):
        raise RuntimeError("One or more synthesized sections failed; partial results remain available")

if __name__=="__main__":
    main()
