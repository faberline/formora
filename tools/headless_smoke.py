#!/usr/bin/env python3
"""CPU CLI/MCP functional checks. Run in CI, without DISPLAY or a GPU build."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable(value):
    if isinstance(value, dict):
        return {k: stable(v) for k, v in value.items() if k != "elapsed_ms"}
    if isinstance(value, list):
        return [stable(v) for v in value]
    return value


def mcp_child():
    binary, scene, receipt = sys.argv[2:]
    command = [binary, "mcp", "--scene", scene]
    child = subprocess.Popen(command, stdin=sys.stdin.buffer, stdout=sys.stdout.buffer, stderr=sys.stderr.buffer)
    record = {"command": command, "pid": child.pid, "waited": False}
    save(Path(receipt), record)
    code = child.wait()
    record.update(waited=True, exit_code=code)
    save(Path(receipt), record)
    return code


async def run(binary, output):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    assert "DISPLAY" not in os.environ and "WAYLAND_DISPLAY" not in os.environ
    output.mkdir(parents=True, exist_ok=False)
    scene = output / "scene.json"
    journal = []

    def cli(name, args, expected=0):
        command = [str(binary), *map(str, args)]
        start = time.monotonic()
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        journal.append({"name": name, "command": command, "waited": True,
                        "exit_code": result.returncode, "expected_exit": expected,
                        "elapsed_ms": (time.monotonic()-start)*1000})
        save(output / "processes.json", journal)
        (output / f"{name}.stdout").write_text(result.stdout)
        (output / f"{name}.stderr").write_text(result.stderr)
        assert result.returncode == expected, (name, result.returncode, result.stderr, result.stdout)
        return json.loads(result.stdout) if result.stdout.strip() else None

    cli("init", ["scene", "init", "--scene", scene, "--demo-room"])
    original = digest(scene)
    full_args = ["headless", "--scene", scene, "--geometry", "--include-world"]
    first = cli("first", full_args)
    assert first["passed"] and all(c["status"] == "passed" for c in first["checks"])
    assert first["geometry"]["vertices"] > 0
    assert len(first["world_matrices"]) == first["counts"]["entities"]
    repeated = cli("repeat-new-process", full_args)
    assert stable(first) == stable(repeated)
    assert digest(scene) == original
    compact = cli("compact", ["headless", "--scene", scene])
    assert compact["passed"] and compact["geometry"] is None
    assert next(c for c in compact["checks"] if c["name"] == "geometry")["status"] == "not_requested"
    zero = cli("zero-size", [*full_args, "--width", "0"], 1)
    assert not zero["passed"] and zero["checks"][0]["status"] == "failed"
    invalid_path = output / "invalid.scene.json"
    invalid = json.loads(scene.read_text())
    invalid["schema_version"] = 999
    save(invalid_path, invalid)
    invalid_hash = digest(invalid_path)
    invalid_report = cli("invalid-source", ["headless", "--scene", invalid_path, "--geometry"], 1)
    assert not invalid_report["passed"] and invalid_report["checks"][0]["name"] == "load"
    assert digest(invalid_path) == invalid_hash and digest(scene) == original
    cli("reject-unknown-option", ["headless", "--scene", scene, "--not-a-flag"], 64)

    receipt = output / "mcp-process.json"
    params = StdioServerParameters(command=sys.executable,
        args=[str(Path(__file__).resolve()), "--mcp-child", str(binary), str(scene), str(receipt)])
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer, read_timeout_seconds=30) as client:
            await client.initialize()
            tools = await client.list_tools()
            assert {t.name for t in tools.tools} == {"scene_inspect", "scene_apply", "scene_undo", "scene_export", "scene_debug"}
            request = {"geometry": True, "include_world": True}
            debug = await client.call_tool("scene_debug", request)
            assert not debug.is_error and stable(debug.structured_content) == stable(first)
            save(output / "mcp-first.json", debug.structured_content)
            # This read succeeds while the MCP server owns the existing writer lock.
            concurrent = cli("read-while-writer-open", full_args)
            assert stable(concurrent) == stable(first) and digest(scene) == original
            bad = await client.call_tool("scene_debug", {"geometry": True, "width": 0})
            assert bad.is_error
            failed = json.loads(bad.content[0].text)
            assert not failed["passed"]
            save(output / "mcp-failed.json", failed)
            assert digest(scene) == original
            authored = json.loads(scene.read_text())
            entity_id = next(k for k,v in authored["entities"].items() if v["content"]["kind"] == "mesh")
            transform = authored["entities"][entity_id]["transform"]
            transform["translation"][0] += 0.25
            changed = await client.call_tool("scene_apply", {"expected_revision": authored["revision"],
                "commands": [{"operation": "set_transform", "id": entity_id, "transform": transform}]})
            assert not changed.is_error
            edited_hash = digest(scene)
            edited = await client.call_tool("scene_debug", request)
            assert not edited.is_error and edited.structured_content["passed"]
            assert edited.structured_content["world_sha256"] != first["world_sha256"]
            assert edited.structured_content["geometry"]["sha256"] != first["geometry"]["sha256"]
            edited_cli = cli("edited-new-process", full_args)
            assert stable(edited_cli) == stable(edited.structured_content)
            assert digest(scene) == edited_hash
            save(output / "mcp-edited.json", edited.structured_content)
    process = json.loads(receipt.read_text())
    assert process["waited"] and process["exit_code"] == 0, process
    assert digest(scene) == edited_hash
    # Public synthetic data. No consumer model data is included in this CI fixture.
    colors = [[0.25, 0.5, 0.75, 1], [0.125, 0.75, 0.375, 1], [0, 0, 1, 1]]
    color_scene = output / "colors.scene.json"
    cli("colors-init", ["scene", "init", "--scene", color_scene])
    asset = {"vertices": {"a": [-1, -1, 0], "b": [1, -1, 0], "c": [0, 1, 0]},
             "triangles": {"face": {"vertices": ["a", "b", "c"], "uv_layers": {},
                 "corner_normals": [[0, 0, 1]] * 3, "corner_colors": colors, "material_slot": None}},
             "material_slots": []}
    color_request = output / "colors-create-request.json"
    save(color_request, {"expected_revision": 0, "commands": [
        {"operation": "set_mesh_asset", "id": "mesh", "asset": asset},
        {"operation": "create_entity", "id": "object", "entity": {
            "name": "Colors", "parent": None,
            "transform": {"translation": [0, 0, 0], "rotation": [0, 0, 0, 1], "scale": [1, 1, 1]},
            "content": {"kind": "mesh", "geometry": {"kind": "asset", "id": "mesh"}, "material": None}}}]})
    cli("colors-create", ["scene", "apply", "--scene", color_scene, "--request", color_request])
    assert json.loads(color_scene.read_text())["mesh_assets"]["mesh"]["triangles"]["face"]["corner_colors"] == colors
    color_args = ["headless", "--scene", color_scene, "--geometry"]
    color_first = cli("colors-cold-reopen", color_args)
    assert color_first["passed"] and color_first["geometry"]["vertices"] == 3
    color_receipt = output / "colors-mcp-process.json"
    color_params = StdioServerParameters(command=sys.executable,
        args=[str(Path(__file__).resolve()), "--mcp-child", str(binary), str(color_scene), str(color_receipt)])
    async with stdio_client(color_params) as (reader, writer):
        async with ClientSession(reader, writer, read_timeout_seconds=30) as client:
            await client.initialize()
            tools = await client.list_tools()
            assert "corner_colors" in str(next(t for t in tools.tools if t.name == "scene_apply").input_schema)
            asset["triangles"]["face"]["corner_colors"] = [[0.75, 0.25, 0.5, 1], [0.375, 0.625, 0.25, 1], [0, 0, 1, 1]]
            revision = json.loads(color_scene.read_text())["revision"]
            applied = await client.call_tool("scene_apply", {"expected_revision": revision,
                "commands": [{"operation": "set_mesh_asset", "id": "mesh", "asset": asset}]})
            assert not applied.is_error
            saved_colors = json.loads(color_scene.read_text())["mesh_assets"]["mesh"]["triangles"]["face"]["corner_colors"]
            assert saved_colors == asset["triangles"]["face"]["corner_colors"]
            color_updated = await client.call_tool("scene_debug", {"geometry": True})
            assert not color_updated.is_error
            assert color_updated.structured_content["geometry"]["sha256"] != color_first["geometry"]["sha256"]
            save(output / "colors-mcp-debug.json", color_updated.structured_content)
            protected_hash = digest(color_scene)
            asset["triangles"]["face"]["corner_colors"][0][0] = 2
            invalid_request = {"expected_revision": revision + 1,
                "commands": [{"operation": "set_mesh_asset", "id": "mesh", "asset": asset}]}
            rejected = await client.call_tool("scene_apply", invalid_request)
            assert rejected.is_error and digest(color_scene) == protected_hash
            save(output / "colors-mcp-rejected.json", rejected.model_dump(mode="json"))
    color_process = json.loads(color_receipt.read_text())
    assert color_process["waited"] and color_process["exit_code"] == 0
    color_reopened = cli("colors-after-mcp-exit", color_args)
    assert stable(color_reopened) == stable(color_updated.structured_content)
    invalid_request_path = output / "colors-invalid-request.json"
    save(invalid_request_path, invalid_request)
    cli("colors-reject-invalid-cli", ["scene", "apply", "--scene", color_scene, "--request", invalid_request_path], 1)
    assert digest(color_scene) == protected_hash
    usd = output / "colors-existing.usda"
    usd.write_text("preserve existing output\n")
    usd_hash = digest(usd)
    rejected_usd = cli("colors-reject-usd", ["scene", "export", "--scene", color_scene,
        "--root", "object", "--format", "usda", "--output", usd], 1)
    assert "corner colors" in str(rejected_usd) and digest(usd) == usd_hash
    assert digest(color_scene) == protected_hash
    save(output / "result.json", {"passed": True, "mode": "headless_cpu",
         "display_variables_absent": True, "cli_mcp_reports_match": True,
         "debug_reads_preserve_files": True, "explicit_edit_changes_world_and_geometry": True,
         "source_before_explicit_edit_sha256": original, "source_after_explicit_edit_sha256": edited_hash,
         "mcp_waited": True, "mcp_exit_code": process["exit_code"]})
    save(output / "colors-result.json", {"passed": True, "cli_create_and_cold_reopen": True,
        "mcp_schema_and_update": True, "rgba_preserved": True, "geometry_hash_changed": True,
        "invalid_cli_mcp_preserve_file": True, "usd_rejects_without_overwrite": True,
        "waited": True, "exit_code": color_process["exit_code"]})
    print(json.dumps({"passed": True, "output": str(output)}))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--mcp-child":
        raise SystemExit(mcp_child())
    if len(sys.argv) != 3:
        raise SystemExit("usage: headless_smoke.py BUILT_BINARY NEW_OUTPUT_DIR")
    asyncio.run(run(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()))
