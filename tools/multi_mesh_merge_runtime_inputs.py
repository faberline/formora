"""Build public setup commands from authored inputs only."""
from multi_mesh_merge_product_inputs import scene, request


def setup(suite, run):
    initial = scene(suite, run)
    commands = [{'operation': 'set_material', 'id': name, 'material': material}
                for name, material in initial['materials'].items()]
    commands += [{'operation': 'set_mesh_asset', 'id': name, 'asset': asset}
                 for name, asset in initial['mesh_assets'].items()]
    commands += [{'operation': 'create_entity', 'id': name, 'entity': entity}
                 for name, entity in initial['entities'].items()]
    commands += [{'operation': 'set_object_context', 'context': initial['object_context']},
                 {'operation': 'set_authoring_context', 'context': initial['authoring_context']}]
    return {'expected_revision': 0, 'commands': commands}


def operation(run):
    return {'expected_revision': 1, 'commands': [request(run)]}
