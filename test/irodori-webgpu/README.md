# Irodori-TTS 500M v3 WebGPU テスト

公開先: https://2rwa.github.io/tmp-speech/test/irodori-webgpu/

既に WebGPU 動作実績のある [ngc-shj/irodori-tts-webgpu](https://github.com/ngc-shj/irodori-tts-webgpu) を再利用する UI 実験。speech.cpp WASM ではなく、ONNX Runtime Web の WebGPU 推論版です。

構築時に pinned upstream の app.mjs, pipeline.mjs, tokenizer とライセンスを取得。Pages 配下で動くように tokenizer の絶対パスのみ書き換えます。モデル本体は Hugging Face の配布元から取得し、ブラウザ Cache Storage に保存されます。初回は約 1GB、動作機器の VRAM/メモリが必要です。

使い方: 許可を得た参照音声ファイルを選択し、短い日本語を入力して生成。音声と WAV ダウンロード、合成時間・RTF とロード時間を表示します。「計測」は DiT/DAC 推定ベンチマークです。

GitHub Actions の構文/構成テストは実際の 1GB モデルを使った音声合成の完走を保証しません。端末ごとの合成検証が必要です。
