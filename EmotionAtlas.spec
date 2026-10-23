# PyInstaller specification. Run from the repository root on macOS.
from pathlib import Path
root = Path(SPECPATH)
a = Analysis([str(root/'app.py')], pathex=[str(root)],
    binaries=[], datas=[(str(root/'assets/emotion-atlas-icon-small.png'), 'assets'), (str(root/'LICENSE'), '.'),
                        (str(root/'THIRD_PARTY_NOTICES.md'), '.'), (str(root/'VERSION'), '.'), (str(root/'licenses'), 'licenses')],
    hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Emotional Atlas', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          target_arch='arm64', codesign_identity=None, entitlements_file=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Emotional Atlas')
app = BUNDLE(coll, name='Emotional Atlas.app', icon=str(root/'assets/emotion-atlas.icns'),
    bundle_identifier='com.github.FL2744.emotion-atlas', version='0.2',
    info_plist={'CFBundleDisplayName':'Emotional Atlas', 'CFBundleShortVersionString':'0.2',
                'CFBundleVersion':'2', 'LSMinimumSystemVersion':'15.0',
                'NSHighResolutionCapable':True, 'NSHumanReadableCopyright':'Copyright 2026 Emotional Atlas contributors'})
