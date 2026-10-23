<p align="center"><img src="assets/emotional-atlas-logo.png" width="100%" alt="Emotional Atlas — constellation icon and retro white wordmark in grayscale"></p>

# Emotional Atlas

**Explore emotional shifts in dreams and literature, paragraph by paragraph.**

Emotional Atlas is a native desktop application that uses **GPT-6 Luna** to infer emotional meaning, identify supporting words and passages, and map paragraphs in an interactive 3D space. It includes text-order animation, PCA views, and resumable analysis sessions in a retro black, white, and gray interface.

[Download macOS v0.2](https://github.com/FL2744/emotion-atlas/releases/tag/v0.2) · [User guide](docs/USER_GUIDE.md) · [Release notes](CHANGELOG.md)

## Features

- Open UTF-8 `.txt` files or paste text; split by blank lines or individual lines.
- Infer intensity, valence, and inward/outward direction with `gpt-6-luna`.
- Inspect emotional components, experiencers, targets, exact evidence, and highlighted signal words.
- Rotate, zoom, and click paragraphs in the 3D plot; open a synchronized expanded plot at up to twice the display area.
- Animate existing results in text order with pause, restart, scrubbing, and adjustable speed. **Playback requires no API key or new inference.**
- Switch to standardized **2D or 3D PCA** of the three emotional scores; inspect component weights and explained variance.
- Save and reopen JSON sessions, resume unfinished analysis, and export paragraph scores or PCA data.
- Keep verified results when an individual paragraph fails evidence validation; unresolved paragraphs are marked **Needs review**.

## Install on macOS

The v0.2 binary targets **Apple Silicon (arm64), macOS 15 or later**. It was built and smoke-tested on macOS 15.6. Intel and other operating systems do not have packaged releases yet.

1. Download `Emotional-Atlas-v0.2-macOS-arm64.zip` from the [v0.2 release](https://github.com/FL2744/emotion-atlas/releases/tag/v0.2).
2. Extract the ZIP and drag **Emotional Atlas.app** into Applications.
3. Open the app.

Python and Tk are bundled; no separate Python installation is needed for this download. The release is **ad-hoc signed, not Developer ID signed or notarized by Apple**. macOS may initially block it. If you trust this release, use macOS **System Settings → Privacy & Security → Open Anyway** after attempting to open it. Do not disable Gatekeeper globally. A SHA-256 checksum accompanies the download.

## First analysis

1. Choose **Open .txt**, or paste a passage.
2. Enter your own OpenAI API key. Your API project must have access to `gpt-6-luna` and sufficient API quota; API use is billed to that project.
3. For a small trial, select **First 12 remaining** and click **Analyze / Resume**.
4. Click a plotted point to inspect the text and why it received its scores.
5. Click **Save session** to preserve the source and results. Reopen that JSON file with **Open session** later.

To view an existing analysis, open its session and press **Play**. You do not need to enter a key or click Analyze. A CSV export is not a resumable session.

## Understanding the plots

| Emotional axis | Range | Meaning |
| --- | --- | --- |
| Valence | −1 to +1 | Unpleasant to pleasant emotional tone |
| Direction | −1 to +1 | Internal/self-focused to directed toward others or the world |
| Intensity | 0 to 1 | Absent to extreme strength of feeling |

Each point is one paragraph. Color also represents original valence. Unknown direction is not treated as zero: the paragraph remains in the table and is omitted from the plot. Mixed feelings are retained as separate emotional components even when net valence is near zero.

**PCA is calculated from these three standardized scores, not text embeddings.** PC1 and PC2 provide a two-dimensional projection; keeping all three components preserves all variance in the three inputs. PCA needs at least three eligible paragraphs and some score variation. See [PCA details](docs/USER_GUIDE.md#pca-views) for exclusions, weighting, and interpretation.

These are model-generated interpretations, not validated psychological measurements or diagnoses. Evidence checking verifies that cited text exists; it does not establish that an interpretation is correct.

## Privacy and reliability

- Your key stays in process memory and is excluded from saved sessions and exports.
- Analysis sends target paragraphs and nearby context directly to OpenAI's Responses API, with `store=false`. OpenAI's applicable API data policies still apply.
- No analytics, cloud storage, or automatic local session saving is implemented.
- Saved sessions include the full source text and analysis. Keep them private if the text is sensitive. The repository excludes session files, exports, environment files, and build outputs by default.
- Long documents are processed incrementally. Nearby context is included, but the model does not maintain whole-book memory.
- Missing or invalid evidence is retried using source-word selection. Unverified results are not assigned fabricated fallback scores.
- Network or account errors pause the run. Stop waits for the in-flight request, up to its 150-second timeout. Interrupted and repair requests may incur API usage.

## Run from source

Requires **Python 3.10+ with Tk**. The application itself uses the Python standard library; no third-party runtime packages are required.

```bash
git clone https://github.com/FL2744/emotion-atlas.git
cd emotion-atlas
python3 app.py
```

On macOS, you can also double-click `Start.command`. Linux distributions may require their `python3-tk` package. Source operation outside macOS is not verified in this release.

## Tests and macOS build

```bash
python3 -m unittest discover -p 'test_*.py' -v

# Build on an Apple Silicon Mac with Python + Tk installed.
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-build.txt
bash scripts/build_macos.sh
```

The build creates `dist/Emotional Atlas.app` and a ZIP in `release/`. It uses PyInstaller and does not require an API key. The app provides an explicit offline release check:

```bash
'dist/Emotional Atlas.app/Contents/MacOS/Emotional Atlas' --smoke-test /tmp/emotion-atlas-smoke.json
```

The smoke test opens and closes its own test window and checks the icon, controls, plot expansion, PCA, and playback using synthetic data. It sends no requests. Unit tests use simulated API responses; live model quality is not proven by these tests. An optional NumPy reference test runs when NumPy is available.

## Project layout

- `app.py` — native Tk interface and interactive plot
- `analysis.py` — model prompt, schema, requests, evidence validation, and sessions
- `pca.py` — dependency-free PCA calculation
- `playback.py` — text-order playback state
- `smoke.py` — offline native release test
- `EmotionAtlas.spec` and `scripts/build_macos.sh` — macOS packaging
- `frankenstein.txt` — optional public-domain sample with its Gutenberg license

## License and credits

Application source and artwork: [MIT](LICENSE). Third-party runtimes and the optional Gutenberg text retain their own terms; see [third-party notices](THIRD_PARTY_NOTICES.md). The application icon was generated with OpenAI's image-generation tool.
