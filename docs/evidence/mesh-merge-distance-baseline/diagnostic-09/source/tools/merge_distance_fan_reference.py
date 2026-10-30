# SPDX-License-Identifier: GPL-2.0-or-later
"""Derive custom normal fan setup from the pinned mesh_normals.cc.

No captured normal or source answer is an input. This models mesh creation,
not normals transferred by the later distance weld operation.
"""
from generate_merge_distance_cases import f32
from merge_distance_normal_reference import add, sub, mul, div, dot, normalize, acos_approx, face_normal, space, encode_normalized, decode


def custom_fans(mesh):
    faces = list(mesh['polygons']); loops = []; by_vertex = {name: [] for name in mesh['vertex_order']}
    edge_name = {frozenset(pair): name for name, pair in mesh['edges'].items()}
    face_normals = {name: face_normal([mesh['vertices'][v] for v in mesh['polygons'][name]['vertices']]) for name in faces}
    for face in faces:
        vertices = mesh['polygons'][face]['vertices']; indices = []
        for i, vertex in enumerate(vertices):
            index = len(loops); indices.append(index); by_vertex[vertex].append(index)
            loops.append({'face': face, 'i': i, 'vertex': vertex, 'previous': vertices[i-1], 'next': vertices[(i+1) % len(vertices)],
                          'edge_prev': edge_name[frozenset((vertices[i-1], vertex))],
                          'edge_next': edge_name[frozenset((vertex, vertices[(i+1) % len(vertices)]))]})
    sharp = set(mesh['sharp_edges'])

    def fans():
        result = []
        for vertex, corners in by_vertex.items():
            if not corners: continue
            edges = {}
            for at in corners:
                loop = loops[at]
                for direction, winding in [('prev', True), ('next', False)]:
                    edge = loop['edge_'+direction]
                    if edge in sharp or not mesh['polygons'][loop['face']]['smooth']:
                        edges[edge] = None; continue
                    if edge not in edges: edges[edge] = [(at, winding)]
                    elif edges[edge] is not None:
                        if len(edges[edge]) > 1 or edges[edge][0][1] == winding: edges[edge] = None
                        else: edges[edge].append((at, winding))
            visited = set()
            for start in corners:
                if start in visited: continue
                current = start; fan = [start]; cyclic = False
                while True:
                    neighbors = edges[loops[current]['edge_next']]
                    if neighbors is None or len(neighbors) != 2: break
                    current = next(at for at, _ in neighbors if at != current)
                    if current == start: cyclic = True; break
                    assert current not in fan, 'invalid cyclic corner traversal'
                    fan.append(current)
                fan.reverse()
                if cyclic:
                    offset = fan.index(min(fan)); fan = fan[offset:]+fan[:offset]
                else:
                    current = start
                    while True:
                        neighbors = edges[loops[current]['edge_prev']]
                        if neighbors is None or len(neighbors) != 2: break
                        current = next(at for at, _ in neighbors if at != current)
                        assert current not in fan, 'invalid open corner traversal'
                        fan.append(current)
                visited.update(fan)
                directions = {}
                for at in fan:
                    loop = loops[at]
                    for direction, other in [('prev', loop['previous']), ('next', loop['next'])]:
                        directions[loop['edge_'+direction]] = normalize([sub(x, y) for x, y in zip(mesh['vertices'][other], mesh['vertices'][vertex])])
                normal = face_normals[loops[fan[0]]['face']]
                if len(fan) > 1:
                    normal = [0., 0., 0.]
                    for at in fan:
                        loop = loops[at]; factor = acos_approx(dot(directions[loop['edge_prev']], directions[loop['edge_next']]))
                        normal = [add(a, mul(b, factor)) for a, b in zip(normal, face_normals[loop['face']])]
                    normal = normalize(normal)
                first, last = loops[fan[0]]['edge_next'], loops[fan[-1]]['edge_prev']
                edge_vectors = [directions[loops[at]['edge_next']] for at in fan] if len(fan) > 1 else []
                if len(fan) > 1 and first != last: edge_vectors.append(directions[last])
                result.append({'corners': fan, 'space': space(normal, directions[first], directions[last], edge_vectors)})
        return result

    original_fans = fans(); automatic = {}
    for fan in original_fans:
        for at in fan['corners']: automatic[at] = fan['space']['normal']
    requested = []
    for at, loop in enumerate(loops):
        raw = mesh['custom_corner_normals'][loop['face']][loop['i']]
        vector = normalize([max(-1., min(1., f32(value))) for value in raw])
        requested.append(automatic[at] if all(value == 0. for value in vector) else vector)
    threshold = sub(1., f32(1e-4))
    for fan in original_fans:
        ordered = list(reversed(fan['corners'])); previous = None; original = None
        for at in ordered:
            if original is None: original = requested[at]
            elif dot(original, requested[at]) < threshold:
                loop = loops[at]; prior_edge = loops[previous]['edge_next']
                sharp.add(prior_edge if prior_edge == loop['edge_prev'] else loop['edge_next'])
                original = requested[at]
            previous = at
        if len(ordered) > 1 and dot(original, requested[ordered[0]]) < threshold:
            loop = loops[ordered[0]]; prior_edge = loops[previous]['edge_next']
            sharp.add(prior_edge if prior_edge == loop['edge_prev'] else loop['edge_next'])
    encoded = {}; decoded = {}; final_fans = fans()
    for fan in final_fans:
        vector = [0., 0., 0.]
        for at in fan['corners']: vector = [add(x, y) for x, y in zip(vector, requested[at])]
        if len(fan['corners']) > 1:
            reciprocal = div(1., float(len(fan['corners']))); vector = [mul(value, reciprocal) for value in vector]
        packed = encode_normalized(fan['space'], vector); normal = decode(fan['space'], packed)
        for at in fan['corners']: encoded[at] = packed; decoded[at] = normal
    pack = lambda table: {face: [table[at] for at, loop in enumerate(loops) if loop['face'] == face] for face in faces}
    return {'encoded': pack(encoded), 'decoded': pack(decoded), 'sharp_edges': sorted(sharp),
            'fan_sizes': [len(fan['corners']) for fan in final_fans], 'scope': 'authored custom normal setup only'}
