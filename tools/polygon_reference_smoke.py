#!/usr/bin/env python3
"""Round-trip pinned reference payloads through Formora. This does NOT generate primitives."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile

from compare_mesh_reference import compare


def transform_from_matrix(matrix):
    scale = [math.sqrt(sum(matrix[row][column]**2 for row in range(3))) for column in range(3)]
    rotation = [[matrix[row][column]/scale[column] for column in range(3)] for row in range(3)]
    determinant = sum(rotation[0][i] * (rotation[1][(i+1)%3]*rotation[2][(i+2)%3] - rotation[1][(i+2)%3]*rotation[2][(i+1)%3]) for i in range(3))
    if determinant < 0:
        scale[0] *= -1
        for row in rotation:
            row[0] *= -1
    trace = sum(rotation[i][i] for i in range(3))
    if trace > 0:
        s = math.sqrt(trace+1)*2
        q = [(rotation[2][1]-rotation[1][2])/s,
             (rotation[0][2]-rotation[2][0])/s,
             (rotation[1][0]-rotation[0][1])/s, s/4]
    else:
        i = max(range(3), key=lambda i: rotation[i][i])
        j, k = (i+1)%3, (i+2)%3
        s = math.sqrt(1+rotation[i][i]-rotation[j][j]-rotation[k][k])*2
        q = [0.0]*4
        q[i] = s/4
        q[j] = (rotation[i][j]+rotation[j][i])/s
        q[k] = (rotation[i][k]+rotation[k][i])/s
        q[3] = (rotation[k][j]-rotation[j][k])/s
    length = math.sqrt(sum(n*n for n in q))
    return {"translation": [matrix[i][3] for i in range(3)],
            "rotation": [n/length for n in q], "scale": scale}


def matrix_from_transform(transform):
    x, y, z, w = transform["rotation"]
    rotation = [[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]]
    return [[rotation[r][c]*transform["scale"][c] for c in range(3)]+[transform["translation"][r]] for r in range(3)]+[[0, 0, 0, 1]]


def to_asset(reference):
    vertices = {f"v{i:06}": p for i, p in enumerate(reference["vertices"])}
    edges = {f"e{i:06}": [f"v{v:06}" for v in edge] for i, edge in enumerate(reference["edges"])}
    polygons, offset = {}, 0
    for i, face in enumerate(reference["faces"]):
        polygons[f"p{i:06}"] = {
            "vertices": [f"v{v:06}" for v in face],
            "normal": reference["face_normals"][i],
            "corner_normals": reference["corner_normals"][offset:offset+len(face)],
            "smooth": reference["smooth_faces"][i], "material_slot": None,
            "uv_layers": {layer["name"]: layer["faces"][i] for layer in reference["uv_layers"]},
        }
        offset += len(face)
    layers = [layer["name"] for layer in reference["uv_layers"]]
    return {"vertices": vertices, "triangles": {}, "edges": edges, "polygons": polygons,
            "uv_layout": {"layers": layers, "active": layers[0] if layers else None}, "material_slots": []}


def from_query(query, transform, run_id):
    asset = query["mesh_asset"]
    vertex_ids = list(asset["vertices"])
    indices = {id: i for i, id in enumerate(vertex_ids)}
    vertices = [asset["vertices"][id] for id in vertex_ids]
    polygons = list(asset.get("polygons", {}).values())
    matrix = matrix_from_transform(transform)
    world = [[sum(matrix[r][c]*p[c] for c in range(3))+matrix[r][3] for r in range(3)] for p in vertices]
    def bounds(points):
        return [[min(p[i] for p in points) for i in range(3)], [max(p[i] for p in points) for i in range(3)]]
    return {
        "run_id": run_id, "vertices": vertices,
        "edges": [[indices[v] for v in e] for e in asset.get("edges", {}).values()],
        "faces": [[indices[v] for v in p["vertices"]] for p in polygons],
        "face_normals": [p["normal"] for p in polygons],
        "corner_normals": [n for p in polygons for n in p["corner_normals"]],
        "smooth_faces": [p["smooth"] for p in polygons],
        "uv_layers": [{"name": name, "faces": [p["uv_layers"][name] for p in polygons]} for name in asset["uv_layout"]["layers"]],
        "triangles": [[indices[asset["polygons"][t["polygon"]]["vertices"][c]] for c in t["corners"]] for t in query["tessellation"]["triangles"]],
        "matrix_world": matrix, "bounds_local": bounds(vertices), "bounds_world": bounds(world),
    }


def run(binary, output):
    root = Path(__file__).resolve().parents[1]
    suite_path = root / "baseline/fixtures/mesh-primitives.json"
    suite = json.loads(suite_path.read_bytes())
    references = root / "baseline/reference/blender-5.2.3/mesh-primitives"
    output.mkdir(parents=True, exist_ok=False)
    reports = []
    def command(*arguments, request=None):
        process = subprocess.run([str(binary), *map(str, arguments)], capture_output=True, text=True,
                                 input=None if request is None else json.dumps(request), check=True)
        return json.loads(process.stdout)
    with tempfile.TemporaryDirectory(prefix="formora-polygon-reference-") as directory:
        for run in suite["runs"]:
            id = run["id"]
            source_path = references / f"{id}.json"
            reference = json.loads(source_path.read_bytes())
            asset = to_asset(reference)
            transform = transform_from_matrix(reference["matrix_world"])
            scene = Path(directory) / f"{id}.scene.json"
            command("scene", "init", "--scene", scene)
            command("scene", "apply", "--scene", scene, "--request", "-", request={
                "expected_revision": 0, "commands": [
                    {"operation": "set_mesh_asset", "id": "reference_payload", "asset": asset},
                    {"operation": "create_entity", "id": "instance", "entity": {
                        "name": id, "parent": None, "transform": transform,
                        "content": {"kind": "mesh", "geometry": {"kind": "asset", "id": "reference_payload"}, "material": None},
                    }},
                ],
            })
            queried = command("scene", "inspect", "--scene", scene, "--mesh-asset", "reference_payload", "--tessellate")
            # Empty optional maps are omitted by the saved format.
            expected = {k: v for k, v in asset.items() if k not in ["edges", "polygons"] or v}
            assert queried["mesh_asset"] == expected, id
            entity = command("scene", "inspect", "--scene", scene, "--entity", "instance")
            candidate = from_query(queried, entity["entity"]["transform"], id)
            assert len(candidate["triangles"]) == len(reference["triangles"]), (id, "triangle count")
            comparison = compare(reference, candidate, suite["comparison"])
            candidate_path = output / f"{id}.json"
            candidate_path.write_text(json.dumps(candidate, allow_nan=False)+"\n")
            reports.append({"id": id, "status": "passed", "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                            "candidate_sha256": hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
                            "tessellated_triangles": len(candidate["triangles"]),
                            "diagnostics": queried["tessellation"]["diagnostics"], **comparison})
    report = {"scope": "Reference payload storage, topology preservation, CLI process reload and Rust polygon tessellation. Not primitive generation.",
              "passed": True, "product_acceptance": "unrun", "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
              "suite_sha256": hashlib.sha256(suite_path.read_bytes()).hexdigest(), "runs": reports,
              "source_files_sha256": {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted([root/"Cargo.toml", root/"Cargo.lock", *[p for p in (root/"src").rglob("*") if p.is_file()]])},
              "adapter_files_sha256": {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ["tools/polygon_reference_smoke.py", "tools/compare_mesh_reference.py", "docs/contracts/polygon-assets.md"]}}
    (output / "report.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps({"payload_round_trips": len(reports), "passed": True, "primitive_generation": "unrun", "output": str(output)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if sys.platform == "win32" and args.binary.suffix != ".exe":
        args.binary = args.binary.with_suffix(".exe")
    run(args.binary.resolve(), args.output.resolve())
