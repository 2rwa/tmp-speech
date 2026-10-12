#!/usr/bin/env bash
set -euo pipefail
# Pin already validated upstream. No pretrained weights are committed to GitHub.
REV=aa3b6390018bb09a2e461c95d1f55992c06e197d
BASE="https://raw.githubusercontent.com/ngc-shj/irodori-tts-webgpu/$REV"
OUT=public/test/irodori-webgpu
mkdir -p "$OUT/runtime" "$OUT/tokenizer/llmjp_tok" "$OUT/LICENSES"
cp test/irodori-webgpu/{index.html,style.css,NOTICE.md} "$OUT/"
get() {
  curl -fsSL --retry 4 --retry-all-errors --connect-timeout 15 --max-time 200     "$BASE/$1" -o "$OUT/$2"
  test -s "$OUT/$2"
}
get space/app.mjs app.mjs
get runtime/pipeline.mjs runtime/pipeline.mjs
for file in tokenizer.json tokenizer_config.json special_tokens_map.json; do
  get "tokenizer/llmjp_tok/$file" "tokenizer/llmjp_tok/$file"
done
get LICENSE LICENSE
for file in Irodori-TTS-LICENSE Semantic-DACVAE-LICENSE llm-jp-3-150m-LICENSE NOTICE; do
  get "LICENSES/$file" "LICENSES/$file"
done
python3 - <<'PY'
from pathlib import Path
app=Path("public/test/irodori-webgpu/app.mjs")
src=app.read_text()
old='env.localModelPath = "/tokenizer/";'
assert src.count(old)==1, "Upstream token path changed; check patch manually"
app.write_text(src.replace(old,'env.localModelPath = new URL("./tokenizer/", import.meta.url).href;'))
home=Path("public/index.html")
if not home.exists():
    home.write_text('<!doctype html><html lang="ja"><meta charset="utf-8"><main><h1>tmp-speech</h1></main></html>')
s=home.read_text()
link='<p style="border:1px solid #4b8597;border-radius:8px;padding:12px"><a href="test/irodori-webgpu/">🎙 Irodori-TTS WebGPUブラウザ合成テスト →</a></p>'
if 'href="test/irodori-webgpu/"' not in s:
    assert "<main>" in s, "Unknown home markup"
    home.write_text(s.replace("<main>","<main>"+link,1))
Path("public/.nojekyll").touch()
PY
echo "Packaged $OUT"
