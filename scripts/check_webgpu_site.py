#!/usr/bin/env python3
"""Offline/static wiring smoke test, not a full WebGPU synthesis benchmark."""
from pathlib import Path
import re

p=Path("public/test/irodori-webgpu")
html=(p/"index.html").read_text()
app=(p/"app.mjs").read_text()
pipe=(p/"runtime/pipeline.mjs").read_text()
for element in ("text","ref","steps","seed","fp16-dit","fp16-dac",
                "fp16-enc","fp16-cond","run","measure","out","dl","log","gpu-info"):
    assert re.search(r'\bid="'+element+'"',html), element
assert 'src="app.mjs"' in html
assert 'onnxruntime-web@1.23.0' in app
assert "huggingface.co/noguchis/irodori-tts-onnx/resolve/main" in app
assert 'new URL("./tokenizer/", import.meta.url).href' in app
assert 'import { IrodoriTTS } from "./runtime/pipeline.mjs"' in app
assert 'export class IrodoriTTS' in pipe
for name in ("tokenizer.json","tokenizer_config.json","special_tokens_map.json"):
    assert (p/"tokenizer/llmjp_tok"/name).is_file(),name
assert (p/"tokenizer/llmjp_tok/tokenizer.json").stat().st_size>6000000
assert (p/"LICENSES/llm-jp-3-150m-LICENSE").is_file()
print("OK: HTML/UI, pinned inference engine, tokenizer, licenses")
