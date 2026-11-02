# Corpus and model sources inspected 2026-10-30

## Human speech

* [Google Speech Commands v2](https://www.tensorflow.org/datasets/catalog/speech_commands):
  CC-BY-4.0, isolated spoken words, 16 kHz WAV. The actual v0.02 archive is
  counted by the download script; do not assume angry/tired/normal are present.
  Source: Warden, *Speech Commands: A Dataset for Limited-Vocabulary Speech
  Recognition*, 2018, https://arxiv.org/abs/1804.03209.
* [MLCommons Multilingual Spoken Words](https://mlcommons.org/datasets/multilingual-spoken-words/):
  CC-BY-4.0, forced-aligned isolated word segments originating from Common Voice.
  The [official HF corpus](https://huggingface.co/datasets/MLCommons/ml_spoken_words)
  is pinned to `0bc9df68e92fd6bb54176bf7eb29e2b9e97cb218`. Opus sources are
  48 kHz, explicitly resampled to 16 kHz. Original speaker IDs are used only for
  partitioning, never identification. Source: Mazumder et al., *Multilingual
  Spoken Words Corpus*, NeurIPS Datasets and Benchmarks 2021.
* [Common Voice / Mozilla Data Collective](https://commonvoice.mozilla.org/fr/datasets)
  and [current source terms](https://commonvoice.mozilla.org/dav/terms): inspected
  as a sentence source; current distribution is through MDC. No MDC account,
  credential or acceptance of account terms was performed. Whole sentences are
  not relabeled as one-word clips. Existing MSWC word alignment supplies the
  aligned source used here. Direct current-CV accent metadata is not available
  in the selected MSWC manifests; French-Canadian evaluation cannot be claimed.
* [Multilingual LibriSpeech / OpenSLR 94](https://openslr.org/94/): CC-BY-4.0,
  English/French audiobook sentences. Investigated as an alternative source;
  not added as isolated commands without alignment. It is also the documented
  source corpus for the selected multi-speaker French Piper voice model.
* [Fluent Speech Commands](https://fluent.ai/fluent-speech-commands-a-dataset-for-spoken-language-understanding-research/):
  inspected as an alternative short-command corpus. Its smart-home action,
  object and location semantics differ from the eight gaze/expression actions.
  No Fluent samples are silently relabeled or counted in the training corpus.

Downloaded raw audio, detailed speaker manifests, original model cards and
archive checksums stay in the external `KWS_DATA` directory. The published
`datasets/dataset_manifest.json` contains only aggregated counts/provenance,
not speaker IDs or raw clips. MSWC metadata availability and retained decoded
samples have separate denominators. Target-bearing English shard selection is
audited against every requested target clip; negatives from those shards are
a selected vocabulary sample, not a random sample of all spoken English.

## Local synthesis

* [Piper voice repository](https://huggingface.co/rhasspy/piper-voices), revision
  `5041a7a49ae5b3a0f30e6837769eb03fdbb231bd`: `fr_FR-mls-medium` has 125 preset
  speakers; `en_US-libritts-high` has 904. The selected 24 preset IDs per model
  are partitioned 16 train / 4 validation / 4 test, with three speaking speeds.
  Their pinned model cards name CC-BY-4.0 source datasets. These represent
  France French and US English; no fr_CA voice is asserted. Piper Siwis stays
  in test because Kokoro ff_siwis uses the same underlying voice source.
  The [pinned complete voice catalog](https://huggingface.co/rhasspy/piper-voices/blob/5041a7a49ae5b3a0f30e6837769eb03fdbb231bd/voices.json)
  has seven French entries, all tagged `fr_FR`, and no `fr_CA` entry.
  `french-voice-catalog.json` records that bounded catalog check; it does not
  imply that every public or commercial TTS engine lacks Canadian voices.
* [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) revision
  `f3ff3571791e39611d31c381e3a41a3af07b4987`: Apache-2.0 weights/preset voices.
  [Voice documentation](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md)
  lists French as a single female voice, `ff_siwis`, with limited non-English
  data and short-utterance caveats. English presets include documented female
  (`af_heart`, `af_bella`) and male (`am_adam`, `am_michael`) voices. The entire
  engine is held out from training. No private voice is cloned.
* [Coqui XTTS-v2](https://huggingface.co/coqui/XTTS-v2): inspected; supports `en`
  and `fr` under the Coqui Public Model License. No French-Canadian preset is
  established by the card. Not used: the preset pipelines suffice and avoid
  introducing a reference-voice cloning requirement or CPML dependency.
* [NVIDIA MagpieTTS multilingual 357M](https://huggingface.co/nvidia/magpie_tts_multilingual_357m):
  inspected; multilingual model under NVIDIA Open Model License, with local
  NeMo deployment documented. Not used in this run: substantially heavier
  dependency/model path than Piper/Kokoro for the 2-vCPU/6-GB WSL environment.

Synthesis provenance includes engine/package version, model revision/hash,
voice ID, text, language, speed, recorded seed, output file and SHA256. Piper
ONNX internal noise generation is not guaranteed reproducible from NumPy's
seed; saved waveform hashes are authoritative for this run. Speed/pitch/gain
and noise augmentation introduce variation; they are not additional speakers.

## Runtime

The existing native Zephyr frontend adapter and its exact pinned Apache-2.0
TFLM source are used directly for training. No ESPHome GPL frontend code or
FreeRTOS task adapter is copied. The independent host TFLM probe uses the same
operator implementations as the native backend, without an XNNPACK delegate.
Host pointer widths and timings differ from the ESP32-P4; host measurements
are identified as such. Existing Whistle measurements are historical repository
evidence and are not a new controlled comparative device benchmark.
