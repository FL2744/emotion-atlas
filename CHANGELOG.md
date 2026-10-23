# Changelog

## v0.3 — 2026-10-23

- Restored colored plot points: red for negative valence, gray for neutral, and blue for positive.
- Colored the app title blue and its Dreams / Literature / Semantic Inference subtitle red.
- Added red and blue constellation points to the icon and README logo.
- Preserved the grayscale interface, layout, and all existing functionality.

## v0.2 — 2026-10-23

- Changed the interface, plot, highlights, and scrollbars to black, white, and gray.
- Updated the application icon and README logo to match the grayscale palette.
- Preserved the retro layout, analysis, saved sessions, PCA, playback, and expanded plot behavior.

## v0.1 — 2026-10-23

Initial public release of Emotional Atlas.

- GPT-6 Luna paragraph inference with contextual evidence and emotional decomposition.
- Interactive 3D emotional plot with clickable points and synchronized 2× expansion.
- Text-order animation of existing analyses, speed control, scrubbing, and neighbor paths.
- Standardized 2D/3D PCA with component interpretation and export.
- Session saving/restoration, resumable batches, CSV export, and review flags.
- Retro royal-blue interface, white monospace text, square controls, and custom icon.
- Self-contained macOS 15+ Apple Silicon application.

### Known limitations

- The macOS binary is ad-hoc signed and not Apple-notarized; Gatekeeper may require explicit user approval.
- Intel Macs do not have a binary in this release.
- Source text and results are not auto-saved. Save the session before exiting.
- Unknown direction excludes a paragraph from emotional and PCA plots.
- Emotions are interpretive model judgments. PCA uses only the three scored features.
- API authentication, billing, and model access are supplied by each user.
