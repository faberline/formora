#!/usr/bin/env python3
"""Capture bounded issue #30 GPU evidence with the actual CLI. No upstream tool is used."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    scene = output / "scene.json"

    def command(*arguments, request=None):
        result = subprocess.run([str(binary), *map(str, arguments)],
                                input=None if request is None else json.dumps(request),
                                capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    command("scene", "init", "--scene", scene, "--demo-room")
    asset = json.loads((root / "tests/fixtures/triangle-asset.json").read_text())
    asset["material_slots"][0] = "door_material"
    commands = [{"operation": "set_mesh_asset", "id": "panel", "asset": asset}]
    for name, location in [("panel_left", [-2, -4, 1]), ("panel_right", [0.6, -4, 1])]:
        commands.append({"operation": "create_entity", "id": name, "entity": {
            "name": name, "parent": None,
            "transform": {"translation": location, "rotation": [2**-0.5, 0, 0, 2**-0.5], "scale": [0.75]*3},
            "content": {"kind": "mesh", "geometry": {"kind": "asset", "id": "panel"}, "material": None},
        }})
    command("scene", "apply", "--scene", scene, "--request", "-",
            request={"expected_revision": 1, "commands": commands})
    first = command("render", "--scene", scene, "--output", output / "before.png", "--width", 960, "--height", 600)
    command("scene", "apply", "--scene", scene, "--request", "-", request={
        "expected_revision": 2, "commands": [{"operation": "set_mesh_vertices", "id": "panel", "positions": {"b": [2, 0, 0.8]}}],
    })
    edited = command("scene", "inspect", "--scene", scene, "--mesh-asset", "panel")
    assert edited["mesh_asset"]["vertices"]["b"] == [2, 0, 0.8]
    after = command("render", "--scene", scene, "--output", output / "after-edit.png", "--width", 960, "--height", 600)
    # Every invocation starts a new process and reads the saved scene.
    reopened = command("render", "--scene", scene, "--output", output / "reopened.png", "--width", 960, "--height", 600)
    assert (output / "after-edit.png").read_bytes() == (output / "reopened.png").read_bytes()
    assert (output / "before.png").read_bytes() != (output / "after-edit.png").read_bytes()
    code_paths = sorted([root / "Cargo.toml", root / "Cargo.lock", * (root / "src").rglob("*.rs")])
    files = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in code_paths}
    manifest = {
        "scope": "issue #30 triangle asset CLI, shared editing, native GPU rendering and process reload",
        "full_product_acceptance": False,
        "platform": platform.platform(), "architecture": platform.machine(),
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "source_files_sha256": files,
        "capture_inputs_sha256": {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in ["tools/mesh_asset_evidence.py", "tests/fixtures/triangle-asset.json", "docs/contracts/mesh-assets.md"]
        },
        "renders": {"before": first, "after_edit": after, "reopened": reopened},
        "edit_visible": True, "reopened_png_identical": True,
        "artifacts": {name: hashlib.sha256((output/name).read_bytes()).hexdigest()
                      for name in ["scene.json", "before.png", "after-edit.png", "reopened.png"]},
        "limits": ["Triangle assets only. Polygon modeling remains unrun.",
                   "UV values are stored; textured drawing is not implemented.",
                   "Native window input, Windows GPU and Linux GPU are unrun for this candidate."],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"output": str(output), "edit_visible": True, "reopened_png_identical": True, "gpu": first["gpu"]}))


if __name__ == "__main__":
    main()
