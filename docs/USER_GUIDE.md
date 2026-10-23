# Emotional Atlas

A native Python desktop app for exploring emotional content in dreams and literature using **gpt-6-luna** inference. No web server, browser, or third-party Python packages are required.

The interface uses a retro black and gray background, white monospace text, and hard-edged controls and panels. The app title is blue and its Dreams / Literature / Semantic Inference subtitle is red. The plot retains a dark rectangular canvas with red-to-gray-to-blue valence markers. Slim arrowless scrollbars use rectangular gray thumbs. Native window frames and file/alert dialogs use macOS styling.

The generated constellation icon is saved in `assets/emotion-atlas-icon.png`. The app also loads a smaller copy as its window icon where supported.

## Start from source

Double-click `Start.command`, or run `python3 app.py` from this directory. Python 3.10+ with Tk is required; the macOS release bundles Python and Tk. The source launcher prefers Python 3.14 when available.

1. Choose **Open .txt** to load a UTF-8 plain text file or paste text.
2. Select paragraph boundaries: blank lines for ordinary paragraphs and line-wrapped ebooks; every line for one-paragraph-per-line files.
3. Enter your OpenAI API key. Choose the first 12 paragraphs for a small trial, or analyze all remaining paragraphs.
4. Click **Analyze / Resume**. API usage is billed to your API project. Your project must have access to `gpt-6-luna`; the app never silently substitutes a model.
5. Rotate the plot by dragging; scroll to zoom. Click a point to inspect its original paragraph, highlighted signal words, exact coordinates, and contextual explanation. You can also select a paragraph in the table and choose **Inspect selected**.
6. **Save session** writes source text, scores, and all evidence to JSON. **Open session** restores results and allows unfinished paragraphs to resume after you re-enter a key. **Export scores to CSV** exports one row per analyzed paragraph.

## Expanded plot

Click **Expand plot 2×** above the plot for a separate synchronized plot window with twice the original canvas area (width and height each increase by √2). When that size exceeds available screen space, the window fits the screen and says so. Selections, PCA mode, filters, and playback stay synchronized; the expanded view includes its own Play / Pause and Reset view buttons. Click **Restore plot**, close the expanded window, or press Escape to return to the main view. This does not reanalyze text.

## Animated text-order playback

Use **Play** below the plot to reveal paragraphs in their original text order. Earlier points remain visible and the current paragraph is highlighted. **Pause** holds the current position; **Restart** clears the plot and plays from paragraph 1. **Show all** restores the full plot. The position slider lets you scrub through the document and pauses playback. Speed ranges from 0.25 to 10 paragraphs per second.

Playback uses existing results and makes no API calls. Saved sessions can be animated immediately after opening, without entering an API key. Paragraphs without accepted scores or directional coordinates still occupy their correct place in the timeline; the playback label explains why no point appears. Filters continue to apply. The optional **Connect neighbors** path only connects consecutive paragraph numbers with visible coordinates, leaving gaps for missing, filtered, or directionless results. Select the Evidence & decomposition tab to watch the text and evidence update alongside the current point. Clicking a point pauses playback for inspection.

Playback position is not saved in the session; reopening a session shows the full plot. After updating the app, save your current session and restart the app to load the new controls.

## PCA views

Choose **PCA 2D** or **PCA 3D** from the View menu above the plot. This performs actual principal component analysis on the existing paragraph-level valence, direction, and intensity scores. Each input is centered and scaled by its sample standard deviation; constant features contribute zero. No new API calls or packages are needed.

PCA requires at least three analyzed paragraphs with known direction and some score variation. Unknown directions are excluded, not filled with zero. The fit uses all eligible analyzed results regardless of filtering or playback position, keeping the basis stable while exploring a completed session. When new inference results arrive, PCA is refitted; active PCA playback pauses so the axes do not silently move during animation.

The 2D view plots PC1 and PC2; axis labels show explained variance. The 3D view includes PC3. **PCA details** shows component weights, feature means/scales, exclusions, and the variance retained in 2D. Click a point for its text, evidence, and actual PC coordinates. Point color still indicates original valence: red for negative, gray for neutral, and blue for positive. **Export PCA** saves paragraph IDs, coordinates, explained variance, and transformation parameters to JSON. Session files retain the original scores, allowing PCA to be recalculated on reopening.

This is PCA of three model-estimated emotional features, not text embeddings. Keeping all three components is a rotation of the standardized data; using two components reduces dimensions. Component signs are arbitrary, and nearly equal eigenvalues can make individual axes unstable. All plotted axes use the same display scale, with actual coordinate bounds shown. Playback and neighboring-point paths also work in PCA views.

## Coordinates and interpretation

- X: valence, −1 (unpleasant) to +1 (pleasant).
- Y: direction, −1 (internal/self-focused) to +1 (directed toward others or the world).
- Z: intensity, 0 (absent) to 1 (extreme strength of feeling).

Each point represents a paragraph. Point color also encodes valence (red negative, gray neutral, blue positive). Unknown direction is `null`, not zero, and those paragraphs are available in the table but excluded from the 3D plot. Mixed emotions are retained as separate components even when their overall valence balances near zero. All axes and results are model interpretations, not validated psychological measurements or diagnoses.

The model decomposes paragraphs into up to five emotional components with experiencer, target/focus, scores, supporting quotes, and signal words. The app checks every quote and signal against the source text. Unique matches that differ only in whitespace or typographic quotes/dashes are restored to the exact original source wording. Paraphrases, omitted words, and ambiguous matches are rejected. When a paragraph fails evidence or score validation, verified neighboring results are retained immediately. The failed paragraph is retried individually using numbered source-word selection: the app reconstructs its quote and signal words directly from the selected original words. Repair requests also incur API usage. If validation still fails, the paragraph is marked Needs review, receives no accepted score, and analysis continues. Select the Needs review filter to inspect these paragraphs; Analyze / Resume retries unresolved paragraphs. Review flags are preserved in saved sessions. Authentication, connection, and other API failures still pause the run. The full prompt, schema, validation, and request code are in `analysis.py`. Uncertainty labels are qualitative model judgments, not calibrated probabilities.

## Large documents

Blank lines preserve paragraph boundaries while wrapped lines within each paragraph are joined. Each request contains up to six target paragraphs, normally at most 18,000 target characters, plus up to 1,200 characters of neighboring context per side. Oversized individual paragraphs are sent alone, up to 250,000 characters; larger paragraphs require manual breaks. Paragraphs are never silently truncated. There is no whole-document semantic memory, so distant references can remain ambiguous.

Analysis runs in a background thread and updates incrementally. Rate-limit and transient server failures are retried up to twice. Stop waits for the current request to finish, up to its 150-second timeout. Completed batches are retained; resume retries unfinished work. Failed or interrupted requests can still incur API usage. Saved sessions can resume across app launches. Unsaved results disappear on exit.

## Key and text handling

The API key is masked in the interface, held in memory for the session, and excluded from exports. It is sent only to `https://api.openai.com/v1/responses`. Text and nearby context are sent to OpenAI when analysis starts. Requests set `store=false`; OpenAI's applicable API data policies still apply. Source text and results are written locally only when you explicitly save or export them. Session files contain your full input text and analysis.

On macOS, HTTPS uses the system CA bundle at `/etc/ssl/cert.pem` in addition to Python's default trust roots. TLS verification remains enabled. If you update source files while the app is running, restart the app to load those changes.

## Included text

`frankenstein.txt` is Mary Shelley's *Frankenstein; or, the Modern Prometheus*, Project Gutenberg ebook #84, downloaded from https://www.gutenberg.org/ebooks/84.txt.utf-8. The full Gutenberg source and license are retained in the file. Open this file with Open .txt if desired; there is no book-specific loading button. Source: https://www.gutenberg.org/ebooks/84.

## Development and verification

Run `python3 -m unittest discover -p 'test_*.py' -v` from this directory. Tests cover paragraph preservation, batch context and resumption, evidence validation, coordinate consistency, API request construction, error handling, and session round trips. Tests use simulated API responses and make no paid inference calls. Live model quality and access depend on the user's API project and require a real run.

Official API references:
- https://developers.openai.com/api/docs/models/gpt-6-luna
- https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses
