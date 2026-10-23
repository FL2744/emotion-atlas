#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m PyInstaller --noconfirm --clean EmotionAtlas.spec
codesign --verify --deep --strict 'dist/Emotional Atlas.app'
mkdir -p release
ditto -c -k --sequesterRsrc --keepParent 'dist/Emotional Atlas.app' 'release/Emotional-Atlas-v0.3-macOS-arm64.zip'
(cd release && shasum -a 256 'Emotional-Atlas-v0.3-macOS-arm64.zip' > SHA256SUMS.txt)
