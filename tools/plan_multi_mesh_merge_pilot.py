#!/usr/bin/env python3
"""Choose deterministic pairwise pilot coverage from authored inputs only."""
import argparse
from itertools import combinations
import json
from pathlib import Path

from generate_multi_mesh_merge_cases import author
from runtime_artifacts import write_json


def plan(suite):
    def tokens(run):
        fields = [run['context'], run['selection'], run['history'], run['parameters']['type'],
                  run['parameters']['uvs'], tuple(run['mode']), run['frame'], run['expected_enum_unavailable']]
        return {(i, repr(a), j, repr(b)) for (i, a), (j, b) in combinations(enumerate(fields), 2)}

    rows = [(run, tokens(run)) for run in suite['runs']]
    uncovered = set().union(*(t for _, t in rows))
    required = len(uncovered)
    chosen = []
    while uncovered:
        run, covered = max(rows, key=lambda row: len(row[1] & uncovered))
        assert covered & uncovered
        chosen.append(run['id'])
        uncovered -= covered
    assert len(chosen) == len(set(chosen))
    return {'scope': 'focused_pairwise_pilot_only', 'authored_cases': len(rows),
            'all_distinct_pair_tokens': required, 'pilot_cases': len(chosen), 'case_ids': sorted(chosen),
            'measured_answers_read': False, 'full_matrix_acceptance': 'unrun'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = plan(author())
    write_json(args.output, value)
    print(json.dumps({k: v for k, v in value.items() if k != 'case_ids'}))
