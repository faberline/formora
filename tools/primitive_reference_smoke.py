#!/usr/bin/env python3
"""Generate primitive geometry through Rust, then compare fixed reference results."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from jsonschema import Draft202012Validator
from compare_mesh_reference import compare
from polygon_reference_smoke import from_query, transform_from_matrix

KINDS = {'plane', 'cube', 'grid', 'circle'}
BOUNDARIES = {'plane_zero_size', 'cube_zero_size', 'grid_zero_size', 'circle_zero_radius',
              'circle_zero_nothing', 'circle_zero_ngon', 'circle_zero_trifan'}
GEOMETRY = ['run_id', 'vertices', 'edges', 'faces', 'face_normals', 'corner_normals',
            'smooth_faces', 'uv_layers', 'matrix_world', 'bounds_local', 'bounds_world', 'triangles']


def command(binary, *arguments, request=None):
    result = subprocess.run([str(binary), *map(str, arguments)], capture_output=True, text=True,
                            input=None if request is None else json.dumps(request), check=True)
    return json.loads(result.stdout)


def arguments_for(run, reference):
    primitive = {'kind': run['operator'], **{k: v for k, v in run['parameters'].items()
                                           if k not in (['location', 'rotation'] if run['operator'] == 'cube' else ['location', 'rotation', 'scale'])}}
    if 'fill_type' in primitive:
        primitive['fill_type'] = primitive['fill_type'].lower()
    return {'expected_revision': 0, 'commands': [
        {'operation': 'create_mesh_primitive', 'id': 'generated', 'primitive': primitive},
        {'operation': 'create_entity', 'id': 'instance', 'entity': {
            'name': run['id'], 'parent': None, 'transform': transform_from_matrix(reference['matrix_world']),
            'content': {'kind': 'mesh', 'geometry': {'kind': 'asset', 'id': 'generated'}, 'material': None},
        }},
    ]}


async def exercise(binary, scene, request, interface):
    command(binary, 'scene', 'init', '--scene', scene)
    if interface == 'cli':
        applied = command(binary, 'scene', 'apply', '--scene', scene, '--request', '-', request=request)
        query = command(binary, 'scene', 'inspect', '--scene', scene, '--mesh-asset', 'generated', '--tessellate')
        entity = command(binary, 'scene', 'inspect', '--scene', scene, '--entity', 'instance')
    else:
        parameters = StdioServerParameters(command=str(binary), args=['mcp', '--scene', str(scene)])
        async with stdio_client(parameters) as (reader, writer):
            async with ClientSession(reader, writer, read_timeout_seconds=10) as client:
                await client.initialize()
                tools = await client.list_tools()
                schema = next(t.input_schema for t in tools.tools if t.name == 'scene_apply')
                Draft202012Validator(schema).validate(request)
                applied = await client.call_tool('scene_apply', request)
                assert not applied.is_error, applied
                applied = applied.structured_content
                response = await client.call_tool('scene_inspect', {'mesh_asset': 'generated', 'tessellate': True})
                assert not response.is_error, response
                query = response.structured_content
                response = await client.call_tool('scene_inspect', {'entity': 'instance'})
                assert not response.is_error
                entity = response.structured_content
    # New process reload is checked for both interfaces after the writer closes.
    reloaded = command(binary, 'scene', 'inspect', '--scene', scene, '--mesh-asset', 'generated', '--tessellate')
    assert reloaded == query
    assert not query['mesh_asset']['recipe']['edited']
    assert applied.get('generation_diagnostics', {}).get('generated', []) == query['mesh_asset'].get('diagnostics', [])
    return query, entity


async def run(binary, output):
    root = Path(__file__).resolve().parents[1]
    first = json.loads((root/'baseline/fixtures/mesh-primitives.json').read_bytes())
    context = json.loads((root/'baseline/fixtures/mesh-creation-contexts.json').read_bytes())
    cases = [(r, root/'baseline/reference/blender-5.2.3/mesh-primitives', first['comparison'], 'primitive_geometry')
             for r in first['runs'] if r['operator'] in KINDS]
    cases += [(r, root/'baseline/reference/blender-5.2.3/mesh-contexts', context['comparison'], 'boundary_geometry_only')
              for r in context['runs'] if r['id'] in BOUNDARIES]
    assert len(cases) == 27
    output.mkdir(parents=True, exist_ok=False)
    records = []
    with tempfile.TemporaryDirectory(prefix='formora-generated-primitives-') as directory:
        for interface in ['cli', 'mcp']:
            for case, reference_directory, limits, scope in cases:
                id = case['id']
                reference_path = reference_directory/(id+'.json')
                source = json.loads(reference_path.read_bytes())
                reference = source if scope == 'primitive_geometry' else {k: source[k] for k in GEOMETRY}
                request = arguments_for(case, source)
                scene = Path(directory)/(interface+'-'+id+'.json')
                query, entity = await exercise(binary, scene, request, interface)
                candidate = from_query(query, entity['entity']['transform'], id)
                candidate['diagnostics'] = query['mesh_asset'].get('diagnostics', [])
                try:
                    comparison = compare(reference, candidate, limits)
                except Exception as error:
                    raise RuntimeError(f"{interface}:{id}:{scope}: {error}") from error
                if scope == 'boundary_geometry_only':
                    assert 'creation_attributes_match_reference' not in comparison
                file = interface+'-'+id+'.json'
                (output/file).write_text(json.dumps(candidate, allow_nan=False)+'\n')
                records.append({'id': id, 'interface': interface, 'scope': scope, 'status': 'passed',
                                'full_context_acceptance': 'unrun', 'file': file,
                                'reference_sha256': hashlib.sha256(reference_path.read_bytes()).hexdigest(),
                                'candidate_sha256': hashlib.sha256((output/file).read_bytes()).hexdigest(),
                                'generated_recipe': query['mesh_asset']['recipe'], **comparison})
    report = {'scope': 'Rust procedural generation, saved parameters and process reload. Finite cases only.',
              'passed': True, 'primitive_cases_per_interface': 20, 'boundary_geometry_subchecks_per_interface': 7,
              'interfaces': ['cli', 'official_mcp_sdk'], 'full_feature_acceptance': 'unrun',
              'full_context_acceptance': 'unrun', 'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
              'source_files_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in sorted([root/'Cargo.toml', root/'Cargo.lock', *[p for p in (root/'src').rglob('*') if p.is_file()]])},
              'adapter_files_sha256': {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in
                                       ['tools/primitive_reference_smoke.py', 'tools/polygon_reference_smoke.py',
                                        'tools/compare_mesh_reference.py', 'docs/contracts/primitive-generation.md']},
              'runs': records}
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'passed': True, 'primitive_cases_per_interface': 20,
                      'boundary_geometry_subchecks_per_interface': 7, 'checks': len(records),
                      'full_feature_acceptance': 'unrun', 'full_context_acceptance': 'unrun'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if sys.platform == 'win32' and args.binary.suffix != '.exe':
        args.binary = args.binary.with_suffix('.exe')
    asyncio.run(run(args.binary.resolve(), args.output.resolve()))
