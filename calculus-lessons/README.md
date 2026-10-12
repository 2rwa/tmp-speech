# 微分・積分のひらがな音声教材

[公開ページ](https://2rwa.github.io/tmp-speech/calculus/) に、基本の微分から定積分・置換積分まで9問を段階順に収録します。

- 問題の数式、解答、導出手順の数式を表示する
- 問題・解説前半・解説後半の3区間に分け、全てひらがなで読み上げる
- speech.cpp v0.8.3、irodori-tts-mf (4 steps)、Ubuntu CPUを使用する
- 各区間をMP3化し、約0.45秒の無音でつないだ1問単位の連続MP3も作る
- 生ログ、合成時間、音声長、成功と失敗の状態を results.json に保存する
- SymPyで数学的な答えを検証する。ひらがな台本は手作業で作成し、文字種を自動検証する

## 実行

GitHub Actions の「Irodori calculus lessons (hiragana TTS + Pages)」を実行するか、このフォルダを main ブランチにコミットします。出力は GitHub Pages と Actions Artifacts に保存します。

音声の正確さ、アクセントと間は自動採点していません。モデルのライセンスに従って利用してください。
