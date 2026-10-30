#!/usr/bin/env python3
"""Author scale-lock inputs without reading any measured answers."""
import argparse
from itertools import product
import json
from pathlib import Path


def author():
    names = ['parent', 'a', 'alias', 'b', 'untouched']
    masks = [[bool(mask & (1 << axis)) for axis in range(3)] for mask in range(8)]
    return {
        'schema_version': 1, 'source_commit': 'e13b728c6880d3084d9d57c30031ed5df8b39dee',
        'scope': 'object_scale_lock_assignment_query_and_native_save_reload',
        'initial_locks': {name: masks[i] for i, name in enumerate(names)},
        'required_cases': 160, 'comparison': {'booleans': 'exact', 'matrices_absolute': 1e-6},
        'base_context': 'active_a',
        'runs': [{'id': f'object_state_{i:03}', 'target': target, 'lock_scale': mask,
                  'mode': mode, 'frame': frame}
                 for i, (target, mask, mode, frame) in enumerate(product(
                     names, masks, ['OBJECT', 'EDIT_MESH'], ['identity', 'noncommuting']))],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with args.output.open('x') as output:
        json.dump(author(), output, indent=2, allow_nan=False)
        output.write('\n')
