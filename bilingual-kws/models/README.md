# Generated command-classifier assets

These small INT8 FlatBuffers are independently trained outputs of this
repository's scripts, not downloaded pretrained speech models, raw audio or
training checkpoints. They follow the repository's default MIT license;
source-corpus and synthesis attribution remains in
[sources.md](../reports/sources.md) and [LICENSES.md](../../LICENSES.md).
This does not relicense the external datasets, TFLM, synthesis engines or voices.

`voice_commands_int8.tflite` is the runtime resource selected by the optional
native firmware build. Its bytes match `dscnn_retrain_int8.tflite` exactly,
SHA256 `e17cbf03e00f5e673b8dd16209e62fb60515fab74c5af5f51732c5da4681b0e8`,
57,408 bytes. The other INT8 candidates reproduce the reported comparisons;
they are not selected automatically and are not all compatible with the fixed
ten-class firmware contract.

Every model has an adjacent JSON manifest with its byte count, SHA256, labels,
tensor quantization, operator list, pinned frontend and public source provenance.
The selected `model_manifest.json` also records the validation-only selection.
The firmware preparation step rejects changed bytes and mismatched contracts.

Keras checkpoints, detailed speaker manifests, corpus clips, private recordings
and intermediate feature arrays remain outside Git. Model availability and host
metrics do not establish physical recognition accuracy or French-Canadian coverage.
