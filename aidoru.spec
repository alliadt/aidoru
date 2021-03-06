# -*- mode: python -*-

import os

block_cipher = None


a = Analysis(['aidoru.py'],
             pathex=[],
             binaries=[],
             datas=[
                ('src/*.css', 'src'),
                ('icons/*', 'icons')
             ],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='aidoru',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          icon='icons/icon.ico',
          console=("CONSOLE" in os.environ))
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='aidoru')
