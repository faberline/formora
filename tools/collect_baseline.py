#!/usr/bin/env python3
"""Collect version-pinned source metadata. This does not review or accept features.

The output directory must be new. Review changes before replacing any frozen data.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib

BLENDER = "https://docs.blender.org/manual/en/5.2/"
UNREAL = "https://dev.epicgames.com/documentation/unreal-engine"
_request_lock = threading.Lock()
_next_request = 0.0


def fetch(url):
    global _next_request
    while True:
        with _request_lock:
            delay = _next_request - time.monotonic()
            if delay <= 0:
                _next_request = time.monotonic() + 1.0
                break
        time.sleep(min(delay, 60.0))
    request = urllib.request.Request(
        url, headers={"User-Agent": "Formora baseline inventory/0.0"}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        if error.code == 429:
            value = error.headers.get("Retry-After", "60")
            try:
                delay = float(value)
            except ValueError:
                try:
                    delay = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
                except (TypeError, ValueError):
                    delay = 60.0
            if not 0 <= delay < float("inf"):
                delay = 60.0
            with _request_lock:
                _next_request = max(_next_request, time.monotonic() + delay)
        raise


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def validate_unreal_document(document):
    url = document["url"]
    if not url.startswith(UNREAL + "/") or pin_unreal(url) != url:
        raise ValueError("seed URL must use the canonical pinned Unreal manual")
    if not any(a.get("version") == "5.8" for a in document["applications"]):
        raise ValueError("seed document does not contain Unreal 5.8")
    if not document["title"].strip():
        raise ValueError("seed document has no title")
    if not re.fullmatch(r"[0-9a-f]{64}", document["response_sha256"]):
        raise ValueError("seed response digest is invalid")
    for name in ["document_id", "revision_id"]:
        if type(document[name]) is not int or document[name] <= 0:
            raise ValueError("seed document and revision IDs must be positive integers")
    for child in document["children"]:
        if not child["title"].strip() or not child["url"].startswith(UNREAL + "/") or pin_unreal(child["url"]) != child["url"]:
            raise ValueError("seed child URL or title is invalid")


def load_unreal_seed(path):
    raw = path.read_bytes()
    metadata = json.loads(raw)
    if metadata.get("schema_version") != 1 or metadata.get("requested_version") != "5.8":
        raise ValueError("seed must be a version 1 Unreal 5.8 capture")
    result = {}
    for document in metadata["documents"]:
        validate_unreal_document(document)
        if document["url"] in result:
            raise ValueError("seed contains duplicate document URLs; audit them before reuse")
        result[document["url"]] = document
    return result, hashlib.sha256(raw).hexdigest()


def collect_unreal(max_depth, seed=None, retrieve=unreal_document, progress=print):
    seed = seed or {}
    sources, documents, failures, seen = {}, {}, [], set()
    frontier = {pin_unreal(UNREAL + "/unreal-engine-5-8-documentation"): "Unreal Engine 5.8 Documentation"}
    reused = 0
    for depth in range(max_depth + 1):
        # Shared children can appear under several parents in the same level.
        # Deduplicate before submitting requests, not after their completion.
        batch = {url: title for url, title in frontier.items() if url not in seen}
        frontier = {}
        for url, title in sorted(batch.items()):
            sources.setdefault(url, source("unreal", title, url))
            seen.add(url)

        def record(url, document):
            validate_unreal_document(document)
            if document["url"] != url:
                raise ValueError("retrieved document URL differs from the requested URL")
            documents[url] = document
            sources[url]["title"] = document["title"]
            for child in document["children"]:
                sources.setdefault(child["url"], source("unreal", child["title"], child["url"]))
                frontier.setdefault(child["url"], child["title"])

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(retrieve, url): url for url in sorted(batch) if url not in seed}
            for url in sorted(batch):
                if url in seed:
                    record(url, seed[url])
                    reused += 1
            for future in as_completed(futures):
                url = futures[future]
                try:
                    record(url, future.result())
                except Exception as error:
                    failures.append({"url": url, "error": str(error)})
        frontier = {url: title for url, title in frontier.items() if url not in seen}
        progress(f"Unreal depth {depth}: {len(documents)} unique documents; {len(failures)} failures; {reused} reused.", flush=True)
        if not frontier:
            break
    return {
        "schema_version": 1,
        "requested_version": "5.8",
        "depth": max_depth,
        "documents": sorted(documents.values(), key=lambda d: d["url"]),
        "failures": sorted(failures, key=lambda d: d["url"]),
        "frontier": [{"title": title, "url": url} for url, title in sorted(frontier.items())],
        "traversal_complete": not frontier and not failures,
        "documents_reused": reused,
        "link_scope": "document_list blocks; inline links and full feature coverage need separate review",
    }, sources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--date", required=True, help="local review date, YYYY-MM-DD")
    parser.add_argument("--unreal-depth", type=int, default=1)
    parser.add_argument("--unreal-seed", type=Path, help="reuse an audited pinned metadata capture")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output directory already exists; frozen data must not be overwritten")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
        parser.error("date must use YYYY-MM-DD")
    if args.unreal_depth < 0:
        parser.error("depth must be non-negative")
    seed, seed_hash = load_unreal_seed(args.unreal_seed) if args.unreal_seed else ({}, None)
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

    metadata, unreal_sources = collect_unreal(args.unreal_depth, seed)
    sources.update(unreal_sources)
    if seed_hash:
        metadata["seed_sha256"] = seed_hash
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
