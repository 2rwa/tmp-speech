#!/usr/bin/env python3
"""Math and script validation before allocating TTS compute."""
from pathlib import Path
import json
import re
from sympy import symbols, diff, integrate, simplify, sqrt, log, Rational

data=[]
for path in sorted(Path("calculus-lessons/data").glob("part*.json")):
    data += json.loads(path.read_text(encoding="utf-8"))
assert len(data)==9, f"expected 9 lessons, got {len(data)}"
assert len({l["id"] for l in data})==9, "lesson IDs must be unique"
for lesson in data:
    assert len(lesson["narration"])==3, lesson["id"]
    assert len(lesson["steps"])>=3, lesson["id"]
    assert lesson["question_tex"] and lesson["answer_tex"]
    for spoken in lesson["narration"]:
        assert 30 < len(spoken) < 240, (lesson["id"],len(spoken))
        assert re.fullmatch(r"[\u3040-\u309f、。！？\s]+",spoken), (lesson["id"],spoken)
    print("READING OK",lesson["id"],[len(v) for v in lesson["narration"]])
x=symbols("x",real=True)
assert simplify(diff(x**3+2*x**2-5*x+7,x)-(3*x**2+4*x-5))==0
f=x**2-2*x+3
assert diff(f,x).subs(x,2)==2 and f.subs(x,2)==3
assert simplify(diff((x**2+1)*(x+2),x)-(3*x**2+4*x+1))==0
assert simplify(diff((3*x+1)**4,x)-12*(3*x+1)**3)==0
assert simplify(diff(2*x**3-2*x**2+3*x,x)-(6*x**2-4*x+3))==0
assert integrate(3*x**2+1,(x,0,2))==10
assert simplify(diff((x**2+1)**4/4,x)-2*x*(x**2+1)**3)==0
assert simplify(integrate(2*x/(x**2+1),(x,0,1))-log(2))==0
assert simplify(integrate(2*x*sqrt(1+x**2),(x,0,1))-Rational(2,3)*(2*sqrt(2)-1))==0
print("MATHEMATICS VERIFIED: 9/9 formulas")
