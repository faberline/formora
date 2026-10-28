#!/usr/bin/env python3
"""Create or update a local development .app from an already-built executable."""
import argparse
import os
from pathlib import Path
import plistlib
import shutil
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--binary',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
if sys.platform!='darwin':parser.error('this development bundle is for macOS')
if not args.binary.is_file():parser.error('binary does not exist; build with --features preview first')
if args.output.suffix!='.app':parser.error('output must end in .app')
contents=args.output/'Contents'
info=contents/'Info.plist'
if args.output.exists():
    if not info.is_file() or plistlib.loads(info.read_bytes()).get('CFBundleIdentifier')!='com.faberline.formora':
        parser.error('existing output is not a Formora development bundle')
(contents/'MacOS').mkdir(parents=True,exist_ok=True)
destination=contents/'MacOS'/'formora'
staged=destination.with_suffix('.new')
shutil.copy2(args.binary,staged)
staged.chmod(0o755)
os.replace(staged,destination)
info.write_bytes(plistlib.dumps({
    'CFBundleDevelopmentRegion':'en',
    'CFBundleExecutable':'formora',
    'CFBundleIdentifier':'com.faberline.formora',
    'CFBundleName':'Formora',
    'CFBundleDisplayName':'Formora',
    'CFBundlePackageType':'APPL',
    'CFBundleShortVersionString':'0.0.0',
    'CFBundleVersion':'1',
    'LSMinimumSystemVersion':'13.0',
    'NSHighResolutionCapable':True,
    'NSPrincipalClass':'NSApplication',
}))
print(args.output.resolve())
