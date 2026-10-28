#!/usr/bin/env python3
"""Capture real concave polygon rendering, notch pixels, edits, reload and failure behavior."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess

from png_pixels import read_rgba8


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    binary = args.binary.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    scene = output/"scene.json"
    commands_run = []
    def command(*arguments, request=None, success=True):
        process = subprocess.run([str(binary), *map(str, arguments)],
                                 input=None if request is None else json.dumps(request), capture_output=True, text=True)
        commands_run.append({"arguments": list(map(str, arguments)), "exit_code": process.returncode,
                             "stdout": process.stdout, "stderr": process.stderr})
        assert process.returncode == (0 if success else 1), commands_run[-1]
        return json.loads(process.stdout) if success else json.loads(process.stdout)["error"]
    command("scene", "init", "--scene", scene)
    asset = json.loads((root/"tests/fixtures/polygon-asset.json").read_text())
    asset["material_slots"][0] = "panel_material"
    identity = {"translation": [0, 0, 0], "rotation": [0, 0, 0, 1], "scale": [1, 1, 1]}
    camera_transform = {**identity, "translation": [1.5, 1.5, 6]}
    commands = [
        {"operation": "set_material", "id": "panel_material", "material": {"base_color": [0.1, 0.5, 0.9, 1], "roughness": 0.6, "metallic": 0}},
        {"operation": "set_mesh_asset", "id": "panel", "asset": asset},
        {"operation": "create_entity", "id": "panel_entity", "entity": {"name": "Concave U", "parent": None, "transform": identity,
            "content": {"kind": "mesh", "geometry": {"kind": "asset", "id": "panel"}, "material": None}}},
        {"operation": "create_entity", "id": "camera", "entity": {"name": "Top view", "parent": None, "transform": camera_transform,
            "content": {"kind": "camera", "vertical_fov_degrees": 60, "near": 0.1, "far": 100}}},
        {"operation": "set_active_camera", "id": "camera"},
    ]
    creation = {"expected_revision": 0, "commands": commands}
    (output/"creation-request.json").write_text(json.dumps(creation, indent=2)+"\n")
    command("scene", "apply", "--scene", scene, "--request", "-", request=creation)
    gpu = command("render", "--scene", scene, "--output", output/"before.png", "--width", 960, "--height", 720)["gpu"]
    before_width, before_height, before = read_rgba8(output/"before.png")
    assert (before_width, before_height) == (960, 720)
    def pixel_for_world(x, y):
        factor = 720/(2*6*math.tan(math.radians(30)))
        return round(480+(x-1.5)*factor), round(360-(y-1.5)*factor)
    background = before(0, 0)
    assertions = {}
    for name, point, filled in [("notch", (1.5, 2), False), ("left_arm", (0.5, 2), True),
                                ("right_arm", (2.5, 2), True), ("base", (1.5, 0.5), True),
                                ("future_cut", (1.75, 0.75), True)]:
        xy = pixel_for_world(*point)
        value = before(*xy)
        assert (value != background) is filled, (name, xy, value, background)
        assertions[name] = {"world_xy": point, "pixel_xy": xy, "before_rgba": value, "filled": filled}
    edit = {"expected_revision": 1, "commands": [{"operation": "set_mesh_vertices", "id": "panel", "positions": {"v4": [2, 0.4, 0]}}]}
    (output/"edit-request.json").write_text(json.dumps(edit, indent=2)+"\n")
    command("scene", "apply", "--scene", scene, "--request", "-", request=edit)
    command("render", "--scene", scene, "--output", output/"after-edit.png", "--width", 960, "--height", 720)
    command("render", "--scene", scene, "--output", output/"reopened.png", "--width", 960, "--height", 720)
    _, _, after = read_rgba8(output/"after-edit.png")
    changed_pixel = pixel_for_world(1.75, 0.75)
    assert after(*changed_pixel) == background
    assertions["future_cut"]["after_rgba"] = after(*changed_pixel)
    assert (output/"before.png").read_bytes() != (output/"after-edit.png").read_bytes()
    assert (output/"after-edit.png").read_bytes() == (output/"reopened.png").read_bytes()
    # A crossing asset is valid authoring data. Its failed preview must publish no partial PNG.
    crossed = output/"crossed.scene.json"
    crossed.write_bytes(scene.read_bytes())
    invalid = json.loads(json.dumps(asset))
    invalid["vertices"]["v1"] = [3, 3, 0]
    invalid["vertices"]["v2"] = [3, 0, 0]
    command("scene", "apply", "--scene", crossed, "--request", "-", request={"expected_revision": 2, "commands": [{"operation": "set_mesh_asset", "id": "panel", "asset": invalid}]})
    saved_crossing = crossed.read_bytes()
    error = command("render", "--scene", crossed, "--output", output/"rejected.png", "--width", 960, "--height", 720, success=False)
    assert "self-intersecting" in error and not (output/"rejected.png").exists()
    protected = output/"protected.png"
    protected.write_bytes((output/"after-edit.png").read_bytes())
    command("render", "--scene", crossed, "--output", protected, "--width", 960, "--height", 720, success=False)
    assert protected.read_bytes() == (output/"after-edit.png").read_bytes()
    assert crossed.read_bytes() == saved_crossing
    code = sorted([root/"Cargo.toml", root/"Cargo.lock", *[p for p in (root/"src").rglob("*") if p.is_file()]])
    artifacts = ["before.png", "after-edit.png", "reopened.png", "scene.json", "crossed.scene.json", "creation-request.json", "edit-request.json"]
    manifest = {"scope": "issue #32 polygon data and native Metal tessellation evidence", "full_product_acceptance": False,
                "platform": platform.platform(), "gpu": gpu, "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                "source_files_sha256": {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in code},
                "capture_inputs_sha256": {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ["tools/polygon_gpu_evidence.py", "tools/png_pixels.py", "tests/fixtures/polygon-asset.json", "docs/contracts/polygon-assets.md"]},
                "pixel_assertions": assertions, "background_rgba": background, "notch_unfilled": True,
                "edit_visible": True, "reopened_png_identical": True, "crossing_rejected_without_partial_output": True,
                "existing_png_preserved_on_failure": True, "saved_crossing_unchanged": True,
                "artifacts": {name: hashlib.sha256((output/name).read_bytes()).hexdigest() for name in artifacts},
                "commands": commands_run,
                "unrun": ["native window input", "Windows GPU", "Linux GPU", "primitive generation", "full modeling parity"]}
    (output/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    print(json.dumps({"gpu": gpu, "notch_unfilled": True, "edit_visible": True, "reload_identical": True, "crossing_failure_preserves_output": True}))


if __name__ == "__main__":
    main()
