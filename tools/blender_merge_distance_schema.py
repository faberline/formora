"""Query actual distance-merge RNA in a fresh native viewport process."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

import bpy

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
assert not args.output.exists()


def capture():
    try:
        windows = [{'screen': window.screen.name, 'areas': [area.type for area in window.screen.areas]}
                   for window in bpy.context.window_manager.windows]
        assert not bpy.app.background and any('VIEW_3D' in window['areas'] for window in windows)
        rna = bpy.ops.mesh.remove_doubles.get_rna_type()
        properties = {}
        for prop in rna.properties:
            if prop.identifier == 'rna_type':
                continue
            item = {'type': prop.type, 'subtype': prop.subtype,
                    'is_readonly': prop.is_readonly, 'is_required': prop.is_required}
            if hasattr(prop, 'is_array') and prop.is_array:
                item['default'] = list(prop.default_array)
                item['array_length'] = prop.array_length
            elif hasattr(prop, 'default'):
                item['default'] = prop.default
            for name in ['hard_min', 'hard_max', 'soft_min', 'soft_max', 'unit', 'precision', 'step']:
                if hasattr(prop, name):
                    item[name] = getattr(prop, name)
            properties[prop.identifier] = item
        report = {'schema_captured': True, 'process_id': os.getpid(), 'argv': sys.argv,
                  'binary_path': bpy.app.binary_path, 'version': list(bpy.app.version),
                  'build_hash': bpy.app.build_hash.decode(), 'background': bpy.app.background,
                  'windows': windows, 'operator': rna.identifier, 'properties': properties,
                  'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'mesh_operations_executed': 0, 'full_source_capture': 'unrun', 'product_acceptance': 'unrun'}
        with args.output.open('x') as stream:
            json.dump(report, stream, indent=2, allow_nan=False); stream.write('\n')
        print(json.dumps({'schema_captured': True, 'process_id': os.getpid(), 'properties': list(properties)}), flush=True)
        bpy.ops.wm.quit_blender()
    except BaseException as error:
        diagnostic = {'schema_captured': False, 'process_id': os.getpid(), 'error': str(error),
                      'traceback': traceback.format_exc(), 'product_acceptance': 'unrun'}
        if not args.output.exists():
            with args.output.open('x') as stream:
                json.dump(diagnostic, stream, indent=2); stream.write('\n')
        print(json.dumps(diagnostic), flush=True)
        os._exit(23)
    return None


bpy.app.timers.register(capture, first_interval=.25)
