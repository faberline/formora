#!/usr/bin/env python3
"""Compare measured meshes without requiring Blender's vertex or face numbering.

Tolerances come from the frozen input suite. This tool does not accept a product
milestone. It compares exported mesh data for one finite fixture set.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path


class Mismatch(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Mismatch(message)


def distance(a, b):
    require(len(a) == len(b), 'vector dimensions differ')
    require(all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                for v in [*a, *b]), 'vectors must contain finite numbers')
    return max((abs(x-y) for x, y in zip(a, b)), default=0.0)


def rotate(values, offset):
    return values[offset:] + values[:offset]


def canonical(face):
    require(len(face) >= 3 and len(set(face)) == len(face), 'face is degenerate')
    offset = min(range(len(face)), key=lambda i: tuple(rotate(face, i)))
    return tuple(rotate(face, offset)), offset


def vertex_uv_signatures(mesh):
    """Necessary vertex labels; face/corner verification still proves the match."""
    if not mesh['uv_layers']:
        return None
    result = [[] for _ in mesh['vertices']]
    for face_index, face in enumerate(mesh['faces']):
        for corner, vertex in enumerate(face):
            values = []
            for layer in mesh['uv_layers']:
                uv = layer['faces'][face_index][corner]
                require(len(uv) == 2, 'UV must have two coordinates')
                if not all(type(value) in [int, float] and math.isfinite(value) for value in uv):
                    return None  # Undefined reference UVs use their explicit policy below.
                values.extend(uv)
            result[vertex].append((len(face), values))
    return result


def uv_signatures_match(actual, expected, tolerance):
    if len(actual) != len(expected):
        return False
    choices = [[j for j, (size, uv) in enumerate(expected)
                if size == a_size and distance(a_uv, uv) <= tolerance]
               for a_size, a_uv in actual]
    if any(not options for options in choices):
        return False
    # Find an injective tolerance match. Sorting/greedy matching can reject
    # valid values on either side of an epsilon boundary.
    matched = {}

    def augment(i, seen):
        for j in choices[i]:
            if j in seen:
                continue
            seen.add(j)
            if j not in matched or augment(matched[j], seen):
                matched[j] = i
                return True
        return False

    return all(augment(i, set()) for i in sorted(range(len(actual)), key=lambda i: len(choices[i])))


def index_mesh(mesh):
    n = len(mesh['vertices'])
    require(n > 0, 'mesh has no vertices')
    for v in mesh['vertices']:
        require(len(v) == 3, 'vertex must have three coordinates')
        distance(v, v)
    neighbors = [set() for _ in range(n)]
    face_sizes = [[] for _ in range(n)]
    edge_counts = Counter()
    for edge in mesh['edges']:
        require(len(edge) == 2, 'edge must have two indices')
        a, b = edge
        require(all(type(i) is int and 0 <= i < n for i in edge) and a != b,
                'edge index is invalid')
        neighbors[a].add(b)
        neighbors[b].add(a)
        edge_counts[tuple(sorted(edge))] += 1
    require(all(count == 1 for count in edge_counts.values()), 'duplicate edge')
    indexed_faces = {}
    require(len(mesh['face_normals']) == len(mesh['faces']) == len(mesh['smooth_faces']),
            'face metadata count differs')
    require(len(mesh['corner_normals']) == sum(map(len, mesh['faces'])),
            'corner normal count differs')
    for layer in mesh['uv_layers']:
        require(len(layer['faces']) == len(mesh['faces']), 'UV face count differs')
        require(all(len(uv) == len(face) for uv, face in zip(layer['faces'], mesh['faces'])),
                'UV corner count differs')
    for field, length in [('vertex_origin', n), ('vertex_selected', n),
                          ('edge_origin', len(mesh['edges'])), ('face_origin', len(mesh['faces'])),
                          ('edge_selected', len(mesh['edges'])),
                          ('face_selected', len(mesh['faces'])), ('face_materials', len(mesh['faces']))]:
        if field in mesh:
            require(len(mesh[field]) == length, field+' count differs')
            if field.endswith('_selected'):
                require(all(type(value) is bool for value in mesh[field]), 'selection must contain booleans')
            elif field.endswith('_origin'):
                require(all(value in ['existing', 'created'] for value in mesh[field]), 'invalid component origin')
            else:
                require(all(type(value) is int and value >= 0 for value in mesh[field]), 'invalid face material')
    corner = 0
    for i, face in enumerate(mesh['faces']):
        require(all(type(v) is int and 0 <= v < n for v in face), 'face index is invalid')
        key, offset = canonical(face)
        require(key not in indexed_faces, 'duplicate oriented face')
        for j, v in enumerate(face):
            require(tuple(sorted((v, face[(j+1) % len(face)]))) in edge_counts,
                    'face boundary edge is missing')
            face_sizes[v].append(len(face))
        indexed_faces[key] = {
            'normal': mesh['face_normals'][i], 'smooth': mesh['smooth_faces'][i],
            'corner_normals': rotate(mesh['corner_normals'][corner:corner+len(face)], offset),
            'uv': [rotate(layer['faces'][i], offset) for layer in mesh['uv_layers']],
            'selected': mesh['face_selected'][i] if 'face_selected' in mesh else None,
            'material': mesh['face_materials'][i] if 'face_materials' in mesh else None,
            'origin': mesh['face_origin'][i] if 'face_origin' in mesh else None,
        }
        corner += len(face)
    signatures = [(len(neighbors[i]), tuple(sorted(face_sizes[i]))) for i in range(n)]
    return neighbors, edge_counts, indexed_faces, signatures


def compare(reference, candidate, comparison, upstream_repeat=False):
    p_tol = comparison['positions_absolute_tolerance_metres']
    n_tol = comparison['normals_absolute_tolerance']
    uv_tol = comparison['uv_absolute_tolerance']
    require(all(isinstance(t, (int, float)) and math.isfinite(t) and t >= 0
                for t in [p_tol, n_tol, uv_tol]), 'invalid frozen tolerance')
    require(len(reference['vertices']) == len(candidate['vertices']), 'vertex count differs')
    require(len(reference['edges']) == len(candidate['edges']), 'edge count differs')
    require(len(reference['faces']) == len(candidate['faces']), 'face count differs')
    require([l['name'] for l in reference['uv_layers']] == [l['name'] for l in candidate['uv_layers']],
            'UV layers differ')
    context_fields = ['creation_kind', 'object_count', 'active_uv_index', 'material_slot_count',
                      'material_slots', 'active_material_index']
    if upstream_repeat:
        context_fields.append('reference_mode_after')
    for field in context_fields:
        if field in reference:
            require(field in candidate and type(candidate[field]) is type(reference[field])
                    and candidate[field] == reference[field], field+' differs')
    for field in ['vertex_origin', 'edge_origin', 'face_origin', 'vertex_selected', 'edge_selected', 'face_selected', 'face_materials']:
        if field in reference:
            require(field in candidate, field+' is missing')
    rn, re, rf, rs = index_mesh(reference)
    cn, ce, _cf, cs = index_mesh(candidate)
    rv, cv = reference['vertices'], candidate['vertices']
    options = []
    for i, v in enumerate(cv):
        matches = [j for j, w in enumerate(rv) if cs[i] == rs[j] and distance(v, w) <= p_tol
                   and all(candidate[field][i] == reference[field][j]
                           for field in ['vertex_origin', 'vertex_selected'] if field in reference)]
        require(matches, f'no position/topology match for candidate vertex {i}')
        options.append(matches)
    if any(len(matches) > 1 for matches in options):
        reference_uv = vertex_uv_signatures(reference)
        candidate_uv = vertex_uv_signatures(candidate)
        if reference_uv is not None and candidate_uv is not None:
            for i, matches in enumerate(options):
                if len(matches) > 1:
                    options[i] = [j for j in matches
                                  if uv_signatures_match(candidate_uv[i], reference_uv[j], uv_tol)]
                    require(options[i], 'UV error prevents a vertex correspondence')
    mapping = {}
    used = set()
    ambiguous = []
    for i, matches in enumerate(options):
        if len(matches) == 1:
            require(matches[0] not in used, 'vertex map is not one-to-one')
            mapping[i] = matches[0]
            used.add(matches[0])
        else:
            ambiguous.append(i)
    # Coincident Suzanne vertices remain distinct. Resolve them through topology,
    # rather than welding them or requiring their original indices.
    ambiguous.sort(key=lambda i: (len(options[i]), -len(cn[i])))
    attempts = 0
    failures = []

    def verify():
        mapped_edges = Counter(tuple(sorted(mapping[v] for v in edge)) for edge in ce)
        require(mapped_edges == re, 'edge topology differs')
        for field in ['edge_selected', 'edge_origin']:
            if field in reference:
                expected_edges = {tuple(sorted(edge)): value for edge, value in
                                  zip(reference['edges'], reference[field])}
                actual_edges = {tuple(sorted(mapping[v] for v in edge)): value for edge, value in
                                zip(candidate['edges'], candidate[field])}
                require(actual_edges == expected_edges, field+' differs')
        mapped = dict(candidate)
        mapped['vertices'] = rv
        mapped['edges'] = [[mapping[v] for v in edge] for edge in candidate['edges']]
        mapped['faces'] = [[mapping[v] for v in face] for face in candidate['faces']]
        _neighbors, _edges, faces, _signatures = index_mesh(mapped)
        require(faces.keys() == rf.keys(), 'oriented face topology differs')
        errors = {'maximum_position_error_metres': 0.0,
                  'maximum_world_position_error_metres': 0.0,
                  'maximum_normal_error': 0.0, 'maximum_face_corner_uv_error': 0.0}
        undefined_uv = 0
        finite_uv = 0
        require(len(reference['matrix_world']) == len(candidate['matrix_world']) == 4,
                'world matrix must have four rows')
        require(all(len(row) == 4 for row in [*reference['matrix_world'], *candidate['matrix_world']]),
                'world matrix must have four columns')
        require(max(distance(a, b) for a, b in zip(reference['matrix_world'], candidate['matrix_world'])) <= p_tol,
                'world matrix differs')

        def world_position(mesh, vertex):
            point = [*mesh['vertices'][vertex], 1.0]
            return [sum(a*b for a, b in zip(row, point)) for row in mesh['matrix_world'][:3]]

        for i, j in mapping.items():
            errors['maximum_position_error_metres'] = max(errors['maximum_position_error_metres'], distance(cv[i], rv[j]))
            errors['maximum_world_position_error_metres'] = max(
                errors['maximum_world_position_error_metres'],
                distance(world_position(candidate, i), world_position(reference, j)))
        require(errors['maximum_world_position_error_metres'] <= p_tol,
                'world position error exceeds frozen tolerance')
        for key, actual in faces.items():
            expected = rf[key]
            require(actual['smooth'] == expected['smooth'], 'face shading mode differs')
            for field in ['selected', 'material', 'origin']:
                if expected[field] is not None:
                    require(actual[field] == expected[field], 'face '+field+' differs')
            errors['maximum_normal_error'] = max(errors['maximum_normal_error'], distance(actual['normal'], expected['normal']))
            for a, b in zip(actual['corner_normals'], expected['corner_normals']):
                errors['maximum_normal_error'] = max(errors['maximum_normal_error'], distance(a, b))
            for aa, bb in zip(actual['uv'], expected['uv']):
                for a, b in zip(aa, bb):
                    require(len(a) == len(b) == 2, 'UV must have two coordinates')
                    for value, target in zip(a, b):
                        if isinstance(target, dict):
                            policy = comparison.get('undefined_uv_policy', {})
                            require(target == {'reference_nonfinite': 'nan'}
                                    and policy.get('finite_fallback') == 0.0
                                    and reference.get('run_id') in policy.get('allowed_run_ids', []),
                                    'undefined upstream UV has no fixed policy')
                            undefined_uv += 1
                            if upstream_repeat:
                                require(value == target, 'upstream undefined UV class differs')
                            else:
                                require(type(value) in [float, int] and math.isfinite(value) and value == 0.0,
                                        'undefined upstream UV requires a finite zero fallback')
                                diagnostics = candidate.get('diagnostics', [])
                                required_diagnostic = policy.get('required_diagnostic')
                                require(isinstance(diagnostics, list)
                                        and isinstance(required_diagnostic, str) and required_diagnostic
                                        and required_diagnostic in diagnostics,
                                        'undefined upstream UV fallback requires a diagnostic')
                        else:
                            finite_uv += 1
                            errors['maximum_face_corner_uv_error'] = max(
                                errors['maximum_face_corner_uv_error'], distance([value], [target]))
        require(errors['maximum_normal_error'] <= n_tol, 'normal error exceeds frozen tolerance')
        require(errors['maximum_face_corner_uv_error'] <= uv_tol, 'UV error exceeds frozen tolerance')
        for key in ['bounds_local', 'bounds_world']:
            require(len(reference[key]) == len(candidate[key]) == 2, 'bounds must have two vectors')
            require(max(distance(a, b) for a, b in zip(reference[key], candidate[key])) <= p_tol,
                    f'{key} differs')
        if 'creation_kind' in reference:
            errors.update({'creation_attributes_match_reference': True,
                           'undefined_reference_uv_components': undefined_uv,
                           'compared_finite_uv_components': finite_uv,
                           'undefined_uv_fallback_verified': undefined_uv > 0 and not upstream_repeat})
            if undefined_uv and not finite_uv:
                errors['maximum_face_corner_uv_error'] = None
        return errors

    def assign(index):
        nonlocal attempts
        attempts += 1
        require(attempts <= 100000, 'ambiguous topology exceeds comparison search limit')
        if index == len(ambiguous):
            try:
                return verify()
            except Mismatch as error:
                failures.append(str(error))
                return None
        i = ambiguous[index]
        for j in options[i]:
            if j in used or any(mapping[n] not in rn[j] for n in cn[i] if n in mapping):
                continue
            mapping[i] = j
            used.add(j)
            result = assign(index+1)
            if result is not None:
                return result
            used.remove(j)
            del mapping[i]
        return None

    errors = assign(0)
    require(errors is not None, failures[0] if failures else 'no bijective topology match')
    return {'oriented_topology_matches_reference': True, **errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--upstream-repeat', action='store_true',
                        help='compare two upstream captures; not a Formora conformance run')
    args = parser.parse_args()
    suite = json.loads(args.suite.read_bytes())
    reports = []
    for run in suite['runs']:
        filename = run['id'] + '.json'
        try:
            result = compare(json.loads((args.reference / filename).read_bytes()),
                             json.loads((args.candidate / filename).read_bytes()), suite['comparison'], args.upstream_repeat)
            reports.append({'id': run['id'], 'status': 'passed', **result})
        except (Mismatch, OSError, ValueError, KeyError, TypeError) as error:
            reports.append({'id': run['id'], 'status': 'failed', 'error': str(error)})
    passed = bool(reports) and all(r['status'] == 'passed' for r in reports)
    print(json.dumps({'comparison_passed': passed, 'runs': reports,
                      'comparison_mode': 'upstream_repeat' if args.upstream_repeat else 'candidate_mesh',
                      'product_acceptance': 'unrun'}, indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
