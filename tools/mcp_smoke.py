#!/usr/bin/env python3
"""Check the built server with the official Python MCP client (mcp==2.3.0)."""
import argparse
import asyncio
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from jsonschema import Draft202012Validator


async def run(binary):
    with tempfile.TemporaryDirectory(prefix="formora-sdk-test-") as directory:
        scene = Path(directory) / "scene.json"
        subprocess.run(
            [str(binary), "scene", "init", "--scene", str(scene), "--demo-room"],
            check=True, capture_output=True, text=True,
        )
        parameters = StdioServerParameters(
            command=str(binary), args=["mcp", "--scene", str(scene)]
        )
        async with stdio_client(parameters) as (reader, writer):
            async with ClientSession(reader, writer, read_timeout_seconds=10) as client:
                initialized = await client.initialize()
                listed = await client.list_tools()
                assert {t.name for t in listed.tools} == {"scene_inspect", "scene_apply", "scene_undo"}
                for tool in listed.tools:
                    Draft202012Validator.check_schema(tool.input_schema)
                inspected = await client.call_tool("scene_inspect", {})
                assert not inspected.is_error
                revision = inspected.structured_content["revision"]
                arguments = {
                    "expected_revision": revision,
                    "commands": [{"operation": "set_door_duration", "id": "front_door", "duration_seconds": 3.0}],
                }
                schema = next(t.input_schema for t in listed.tools if t.name == "scene_apply")
                Draft202012Validator(schema).validate(arguments)
                changed = await client.call_tool("scene_apply", arguments)
                assert not changed.is_error
                assert changed.structured_content["revision"] == revision + 1
                stale = await client.call_tool("scene_apply", arguments)
                assert stale.is_error
                undone = await client.call_tool("scene_undo", {"expected_revision": revision + 1})
                assert not undone.is_error
                assert undone.structured_content["revision"] == revision + 2
                after = await client.call_tool("scene_inspect", {})
                assert after.structured_content["scene"]["doors"]["front_door"]["duration_seconds"] == 1.0
                protocol = initialized.protocol_version
        loaded = json.loads(subprocess.check_output(
            [str(binary), "scene", "inspect", "--scene", str(scene)], text=True
        ))
        assert loaded["revision"] == revision + 2
        assert loaded["scene"]["doors"]["front_door"]["duration_seconds"] == 1.0
        print(json.dumps({
            "sdk_version": importlib.metadata.version("mcp"),
            "protocol_version": protocol,
            "initialize": "passed", "discovery": "passed", "input_schemas": "passed",
            "inspect": "passed", "apply": "passed", "stale_revision": "passed",
            "undo": "passed", "reload": "passed", "product_milestone_acceptance": False,
        }))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    args = parser.parse_args()
    if sys.platform == "win32" and args.binary.suffix != ".exe":
        args.binary = args.binary.with_suffix(".exe")
    asyncio.run(run(args.binary.resolve()))
