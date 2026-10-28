#!/usr/bin/env python3
"""Collect version-pinned source metadata. This does not review or accept features.

The output directory must be new. Review changes before replacing any frozen data.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import tempfile
import urllib.parse
import urllib.request
import zlib

BLENDER = "https://docs.blender.org/manual/en/5.2/"
UNREAL = "https://dev.epicgames.com/documentation/unreal-engine"


def fetch(url):
    request = urllib.request.Request(
        url, headers={"User-Agent": "Formora baseline inventory/0.0"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def source(product, title, url):
    return {
        "id": product + ":" + hashlib.sha256(url.encode()).hexdigest()[:20],
        "product": product,
        "title": title,
        "url": url,
        "decision": "pending",
        "rationale": "",
        "feature_ids": [],
    }


class StateParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_state = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("id") == "serverApp-state":
            self.in_state = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_state = False

    def handle_data(self, data):
        if self.in_state:
            self.parts.append(data)


def unreal_document(url):
    raw = fetch(url)
    parser = StateParser()
    parser.feed(raw.decode())
    state = json.loads("".join(parser.parts))
    candidates = [
        v["b"]
        for v in state.values()
        if isinstance(v, dict)
        and isinstance(v.get("b"), dict)
        and "blocks" in v["b"]
        and "applications" in v["b"]
    ]
    if len(candidates) != 1:
        raise ValueError(f"expected one official document: {url}")
    doc = candidates[0]
    if not any(a.get("version") == "5.8" for a in doc["applications"]):
        raise ValueError(f"server did not return the pinned Unreal version: {url}")
    links = []
    for block in doc["blocks"]:
        if block.get("type") == "document_list":
            for item in block.get("items", []):
                if item.get("document_url", "").startswith(UNREAL + "/"):
                    links.append((item["title"], pin_unreal(item["document_url"])))
    return {
        "url": url,
        "title": doc["title"],
        "document_id": doc["id"],
        "revision_id": doc["revision_id"],
        "applications": doc["applications"],
        "response_sha256": hashlib.sha256(raw).hexdigest(),
        "children": [{"title": t, "url": u} for t, u in links],
    }


def pin_unreal(url):
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query)
    query = [(k, v) for k, v in query if k not in ("application_version", "lang")]
    query.append(("application_version", "5.8"))
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), urllib.parse.urlencode(query), "")
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--date", required=True, help="local review date, YYYY-MM-DD")
    parser.add_argument("--unreal-depth", type=int, default=1)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output directory already exists; frozen data must not be overwritten")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
        parser.error("date must use YYYY-MM-DD")
    if args.unreal_depth < 0:
        parser.error("depth must be non-negative")
    destination = args.output
    destination.parent.mkdir(parents=True, exist_ok=True)
    args.output = Path(tempfile.mkdtemp(prefix="formora-baseline-", dir="/private/tmp"))
    source_dir = args.output / "sources"
    source_dir.mkdir()
    artifacts = []

    def artifact(name, url, raw):
        (source_dir / name).write_bytes(raw)
        artifacts.append({
            "path": "baseline/sources/" + name,
            "url": url,
            "sha256": hashlib.sha256(raw).hexdigest(),
        })

    inventory_url = BLENDER + "objects.inv"
    raw = fetch(inventory_url)
    header = raw.split(b"\n", 4)
    if len(header) != 5 or header[0] != b"# Sphinx inventory version 2" or header[2] != b"# Version: 5.2":
        raise ValueError("Blender inventory did not match the pinned version")
    artifact("blender-5.2-objects.inv", inventory_url, raw)
    sources = {}
    records = []
    for line in zlib.decompress(header[4]).decode().splitlines():
        match = re.fullmatch(r"(\S+) (\S+:\S+) (-?\d+) (\S+) (.*)", line)
        if match:
            records.append(list(match.groups()))
        elif records:
            records[-1][4] += " " + line
        else:
            raise ValueError("unrecognized record at start of Blender inventory")
    for name, kind, _priority, uri, title in records:
        if kind not in ("std:doc", "std:label"):
            continue
        if uri.endswith("$"):
            uri = uri[:-1] + name
        url = urllib.parse.urljoin(BLENDER, uri)
        if not url.startswith(BLENDER):
            raise ValueError("Blender source escaped its pinned manual")
        entry = source("blender", name if title == "-" else title, url)
        sources.setdefault(url, entry)
    checksum_url = "https://download.blender.org/release/Blender5.2/blender-5.2.3.sha256"
    artifact("blender-5.2.3.sha256", checksum_url, fetch(checksum_url))
    print(f"Blender: {len(sources)} source entries; all await review.", flush=True)

    documents, failures, seen = [], [], set()
    frontier = [("Unreal Engine 5.8 Documentation", pin_unreal(UNREAL + "/unreal-engine-5-8-documentation"))]
    for depth in range(args.unreal_depth + 1):
        batch = [(t, u) for t, u in frontier if u not in seen]
        frontier = []
        for title, url in batch:
            sources.setdefault(url, source("unreal", title, url))
            seen.add(url)
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(unreal_document, url): url for _, url in batch}
            for future in as_completed(futures):
                url = futures[future]
                try:
                    document = future.result()
                    documents.append(document)
                    sources[url]["title"] = document["title"]
                    for child in document["children"]:
                        sources.setdefault(child["url"], source("unreal", child["title"], child["url"]))
                        frontier.append((child["title"], child["url"]))
                except Exception as error:
                    failures.append({"url": url, "error": str(error)})
        print(f"Unreal depth {depth}: {len(documents)} retrieved; {len(failures)} failures.", flush=True)
    metadata = {
        "schema_version": 1,
        "requested_version": "5.8",
        "depth": args.unreal_depth,
        "documents": sorted(documents, key=lambda d: d["url"]),
        "failures": sorted(failures, key=lambda d: d["url"]),
        "traversal_complete": not frontier and not failures,
    }
    artifact("unreal-5.8-documents.json", pin_unreal(UNREAL), (json.dumps(metadata, ensure_ascii=False, indent=2) + "\n").encode())
    manifest = {"schema_version": 1, "products": [
        {"id": product, "retrieval_complete": complete,
         "source_ids": sorted(s["id"] for s in sources.values() if s["product"] == product)}
        for product, complete in [("blender", True), ("unreal", metadata["traversal_complete"])]
    ]}
    artifact("source-manifest.json", inventory_url, (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode())
    write_json(args.output / "lock.json", {
        "schema_version": 1,
        "frozen_at": args.date,
        "products": [
            {"id": "blender", "version": "5.2.3", "manual_root": BLENDER,
             "release_url": "https://www.blender.org/releases/", "release_status": "stable"},
            {"id": "unreal", "version": "5.8", "manual_root": UNREAL,
             "release_url": "https://www.unrealengine.com/news/unreal-engine-5-8-is-now-available", "release_status": "stable"},
        ],
        "platforms": ["macos", "windows", "linux"],
        "exclusions": ["native_project_compatibility", "existing_scripts_and_plugins", "operator_gui_parity", "mobile", "xr", "consoles"],
        "source_manifest_path": "baseline/sources/source-manifest.json",
        "artifacts": artifacts,
    })
    write_json(args.output / "inventory.json", {
        "schema_version": 1,
        "complete_products": [],
        "sources": sorted(sources.values(), key=lambda s: (s["product"], s["url"])),
    })
    write_json(args.output / "catalog.json", {"schema_version": 1, "features": []})
    args.output.rename(destination)
    print(f"Collected {len(sources)} entries. Baseline is incomplete; no feature is accepted.", flush=True)


if __name__ == "__main__":
    main()
