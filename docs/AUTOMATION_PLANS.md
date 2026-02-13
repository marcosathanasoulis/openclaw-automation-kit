# Automation Plans

Each automation directory must include:
- `manifest.json`
- input schema
- output schema
- runner entrypoint exposing `run(context, inputs)`

`run()` must return a JSON-serializable dict.

Required result keys are automation-specific and validated by the output schema.
