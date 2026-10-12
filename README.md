# tmp-speech

[speech.cpp](https://github.com/nyosegawa/speech.cpp) / Irodori-TTS CPU benchmark on GitHub Actions.

- **Results and playable WAV:** https://2rwa.github.io/tmp-speech/
- **Workflow:** [speech.cpp CPU benchmark + Pages](../../actions/workflows/benchmark.yml)
- **Models:** `irodori-tts-mf` (4 steps) and `irodori-tts` (16 steps).
- **Runner:** GitHub-hosted `ubuntu-24.04`, CPU backend; no Mac runner or GPU.
- **Output:** `results.json`, raw logs, and generated WAV in Actions artifacts and Pages.

## What is measured?

Each model is downloaded once, then two Japanese samples are generated in separate CLI processes. The page reports command wall-clock time (including model startup), generated WAV duration, **wall RTF**, plus any first-audio/RTF values reported in speech.cpp logs. The first model download is **not** counted in generation timings.

The CPU measurements here must not be compared directly to speech.cpp's Metal/Vulkan bench: its `speech-bench` runs with a resident model, different prompts, and different hardware.

## Run again

Select **Actions → speech.cpp CPU benchmark + Pages → Run workflow**. Results deploy automatically to GitHub Pages after the benchmark. Verify Pages **Settings → Pages → Source = GitHub Actions**.

Speech.cpp release is pinned to **v0.8.3** and its download SHA256 is verified against the official release. Each synthesis is limited to 600 seconds; failed and timed-out attempts are reported instead of being represented as zeros.

See [scripts/benchmark.py](scripts/benchmark.py) for the exact text, seed, and measurement definitions.

Irodori-TTS models may have usage restrictions; do not use someone else's voice without permission.
