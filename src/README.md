# Eksamiks valmis: source

- `data/`: lesson and exam content (JSON). `data/parts/` holds lessons 11–30.
- `template.html`: the app; `/*__DATA__*/` is replaced with the merged data.
- Build: `python3 src/build.py src/data src/template.html index.html`
- Audio: `python3 src/gen_audio.py src/data audio` (TartuNLP Neurokõne TTS; set `WITH_WORDS=1` for word/example clips). Writes `data/audio.json`.
