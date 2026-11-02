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
    save(output / "result.json", {"passed": True, "mode": "headless_cpu",
         "display_variables_absent": True, "cli_mcp_reports_match": True,
         "debug_reads_preserve_files": True, "explicit_edit_changes_world_and_geometry": True,
         "source_before_explicit_edit_sha256": original, "source_after_explicit_edit_sha256": edited_hash,
         "mcp_waited": True, "mcp_exit_code": process["exit_code"]})
    print(json.dumps({"passed": True, "output": str(output)}))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--mcp-child":
        raise SystemExit(mcp_child())
    if len(sys.argv) != 3:
        raise SystemExit("usage: headless_smoke.py BUILT_BINARY NEW_OUTPUT_DIR")
    asyncio.run(run(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()))
