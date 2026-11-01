"""Data-only provenance check using unchanged original adapters. CI only."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
from rotation_snap_runtime import setup,request_for

ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'baseline/static-usd-macos-axis-angle'
def load(path):return json.loads(path.read_text())
def sha(raw):return hashlib.sha256(raw).hexdigest()
def phases(native):
    return {phase:{'objects':native[phase]['objects'],
        'rotation_channels':native[phase]['rotation_channels'],
        'world_vertices':{name:m['world_vertices_metres'] for name,m in native[phase]['meshes'].items()}}
        for phase in ['before','after']}
def forbidden(*args,**kwargs):
    raise AssertionError('reference verification cannot launch a product/source process')
subprocess.Popen=forbidden
subprocess.run=forbidden
subprocess.check_output=forbidden
subprocess.check_call=forbidden
focused_pins=load(folder/'source-pins.json')
for name,digest in focused_pins['pins'].items():
    assert sha((ROOT/name).read_bytes())==digest,name
assert sha((folder/'fixtures.json').read_bytes())==focused_pins['fixtures_sha256']
suite=load(ROOT/'baseline/fixtures/snap-rotation.json')
cases={c['id']:c for c in suite['runs']}
assert len(cases)==2496
focused=load(folder/'fixtures.json')
assert len(focused)==17
for fixture in focused:
    case=cases[fixture['id']]
    assert setup(suite,case)==fixture['setup']
    assert request_for(case)==fixture['request']
    assert len(fixture['references'])==2
    for reference in fixture['references']:
        native=json.loads(gzip.decompress((ROOT/reference['source']).read_bytes()))
        assert native['run']==case and reference['phases']==phases(native)

pins=load(folder/'all-world-source-pins.json')
assert sha((ROOT/'baseline/fixtures/snap-rotation.json').read_bytes())==pins['suite_sha256']
packed=(folder/'all-world-fixtures.json.gz').read_bytes()
assert len(packed)==pins['gzip_bytes'] and sha(packed)==pins['gzip_sha256']
raw=gzip.decompress(packed)
assert len(raw)==pins['decoded_bytes'] and sha(raw)==pins['decoded_sha256']
fixtures=json.loads(raw)
del raw
assert len(fixtures)==2496 and {f['id'] for f in fixtures}==set(cases)
# The run catalog schedules cases; no adapter reads it to build a scene.
# Avoid copying that unrelated2496-row catalog2496 times. Every original case
# and every authoring field remains. Exact equality below checks all outputs
# against the pre-code full-catalog construction, not a product result.
common={k:v for k,v in suite.items() if k!='runs'}
for fixture in fixtures:
    case=cases[fixture['id']]
    assert setup(common,case)==fixture['setup'],fixture['id']
    assert request_for(case)==fixture['request'],fixture['id']
    assert len(fixture['references'])==2
    for reference in fixture['references']:
        raw=(ROOT/reference['source']).read_bytes()
        assert sha(raw)==reference['source_sha256'],reference['source']
        native=json.loads(gzip.decompress(raw))
        assert native['run']==case
        assert reference['phases']==phases(native),reference['source']
print(json.dumps({'passed':True,'original_adapter_inputs':2496,'native_source_captures':4992,
    'focused_full_catalog_controls':17,'product_execution':False,
    'scope':'source/input provenance only; not product or timing acceptance'}))
