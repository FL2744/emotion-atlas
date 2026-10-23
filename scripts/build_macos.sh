#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m PyInstaller --noconfirm --clean EmotionAtlas.spec
codesign --verify --deep --strict 'dist/Emotion Atlas.app'
mkdir -p release
ditto -c -k --sequesterRsrc --keepParent 'dist/Emotion Atlas.app' 'release/Emotion-Atlas-v0.1-macOS-arm64.zip'
(cd release && shasum -a 256 'Emotion-Atlas-v0.1-macOS-arm64.zip' > SHA256SUMS.txt)
