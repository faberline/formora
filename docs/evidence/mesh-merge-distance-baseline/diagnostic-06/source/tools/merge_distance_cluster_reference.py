# SPDX-License-Identifier: GPL-2.0-or-later
"""Source-only scalar distance-group model from the fixed Blender sources.

This derives vertex targets and positions. It does not accept topology,
attribute interpolation, custom normals or a Rust product operation.
"""
from generate_merge_distance_cases import f32
from merge_distance_normal_reference import add, sub, mul, div, dot


def squared(a, b):
    delta = [sub(x, y) for x, y in zip(a, b)]
    return dot(delta, delta)


class Tree:
    """Preserve pinned partition and traversal order, including equal axes."""
    def __init__(self, points):
        self.nodes = [{'index': i, 'co': p, 'd': 0, 'left': None, 'right': None} for i, p in enumerate(points)]
        self.root = self.balance(0, len(points), 0)

    def balance(self, start, length, axis):
        if length == 0: return None
        if length == 1: return start
        nodes = self.nodes; left = 0; right = length-1; median = length//2
        def swap(i, j):
            a, b = nodes[start+i], nodes[start+j]
            for key in ['index', 'co', 'left', 'right']: a[key], b[key] = b[key], a[key]
        while right > left:
            pivot = nodes[start+right]['co'][axis]; i = left-1; j = right
            while True:
                i += 1
                while nodes[start+i]['co'][axis] < pivot: i += 1
                j -= 1
                while nodes[start+j]['co'][axis] > pivot and j > left: j -= 1
                if i >= j: break
                swap(i, j)
            swap(i, right)
            if i >= median: right = i-1
            if i <= median: left = i+1
        at = start+median; nodes[at]['d'] = axis
        nodes[at]['left'] = self.balance(start, median, (axis+1) % 3)
        nodes[at]['right'] = self.balance(at+1, length-median-1, (axis+1) % 3)
        return at

    def within(self, point, distance):
        stack = [] if self.root is None else [self.root]; limit = mul(distance, distance)
        while stack:
            node = self.nodes[stack.pop()]; axis = node['d']
            if add(point[axis], distance) < node['co'][axis]:
                if node['left'] is not None: stack.append(node['left'])
            elif sub(point[axis], distance) > node['co'][axis]:
                if node['right'] is not None: stack.append(node['right'])
            else:
                delta = squared(node['co'], point)
                if delta <= limit: yield node['index'], delta
                if node['left'] is not None: stack.append(node['left'])
                if node['right'] is not None: stack.append(node['right'])


def targets(points, distance, keep):
    tree = Tree(points); duplicates = [i if i in keep else -1 for i in range(len(points))]
    if keep:
        best = {}
        for node in tree.nodes:
            index = node['index']
            if duplicates[index] != index: continue
            for neighbor, delta in tree.within(points[index], distance):
                previous = duplicates[neighbor]
                if previous == -1 or (previous != neighbor and
                    (delta < best[neighbor] or (delta == best[neighbor] and index < previous))):
                    duplicates[neighbor] = index; best[neighbor] = delta
    for node in tree.nodes:
        index = node['index']
        if duplicates[index] != -1: continue
        cluster = [neighbor for neighbor, _ in tree.within(points[index], distance) if duplicates[neighbor] == -1]
        if not cluster: continue
        # The pinned callback appends the search origin after the range query.
        # Do not replace this ordered list with a set or a transitive component.
        cluster.append(index)
        if len(cluster) == 2:
            target = min(cluster)
        else:
            centroid = [0., 0., 0.]
            for candidate in cluster:
                centroid = [add(a, b) for a, b in zip(centroid, points[candidate])]
            centroid = [div(value, float(len(cluster))) for value in centroid]
            target = cluster[-1]; best_distance = squared(centroid, points[target])
            for candidate in cluster[:-1]:
                delta = squared(centroid, points[candidate])
                if delta < best_distance or (delta == best_distance and candidate < target):
                    target = candidate; best_distance = delta
        for candidate in cluster: duplicates[candidate] = target
    return {index: target for index, target in enumerate(duplicates) if target not in [-1, index]}


def vertex_result(mesh, intended, parameters):
    names = mesh['vertex_order']; selected = set(intended['selected']['VERT'])
    if not selected:
        return {'vertices': mesh['vertices'], 'removed': 0, 'targets': {}, 'classification': 'skipped_empty_selection'}
    unselected = parameters.get('use_unselected', False)
    indices = list(range(len(names))) if unselected else [i for i, name in enumerate(names) if name in selected]
    points = [mesh['vertices'][names[i]] for i in indices]
    keep = {i for i, at in enumerate(indices) if names[at] not in selected} if unselected else set()
    distance = max(f32(1e-6), min(50., f32(parameters.get('threshold', 1e-4))))
    local = targets(points, distance, keep)
    mapping = {indices[index]: indices[target] for index, target in local.items()}
    survivors = [i for i in range(len(names)) if i not in mapping]
    positions = {}
    for i, survivor in enumerate(survivors):
        point = mesh['vertices'][names[survivor]].copy()
        duplicates = [at for at in range(len(names)) if mapping.get(at) == survivor]
        if parameters.get('use_centroid', True) and duplicates:
            for at in duplicates: point = [add(x, y) for x, y in zip(point, mesh['vertices'][names[at]])]
            reciprocal = div(1., float(len(duplicates)+1)); point = [mul(value, reciprocal) for value in point]
        positions[f'v{i:06}'] = point
    return {'vertices': positions, 'removed': len(mapping),
            'targets': {names[index]: names[target] for index, target in mapping.items()},
            'classification': 'merged' if mapping else 'finished_unchanged'}
