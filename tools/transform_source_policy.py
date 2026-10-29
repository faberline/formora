"""Human-approved handling of a specific frozen-source defect, never a general error waiver."""

ERROR = 'mesh transform rotation cannot constrain all three axes: undefined Blender 5.2.3 source behavior'
POLICY = 'human_approved_undefined_rotation_rejection'


def undefined_rotation(run):
    parameters = run.get('parameters', {})
    if run.get('operator') != 'rotate' or not isinstance(parameters, dict):
        return False
    mask = parameters.get('constraint_axis')
    return type(mask) is list and len(mask) == 3 and all(value is True for value in mask)


def require_rejection(run, request, before, after, result, error):
    assert undefined_rotation(run), 'policy does not apply to this authored input'
    command, = request['commands']
    transform = command['transform']
    assert command['operation'] == 'transform_mesh' and transform['change']['kind'] == 'rotate'
    mask = transform['constraint_axis']
    assert type(mask) is list and len(mask) == 3 and all(value is True for value in mask)
    assert error == ERROR, 'undefined source rotation requires the exact explicit error'
    assert result is None, 'a rejected rotation cannot publish a success result'
    assert before == after, 'a rejected rotation changed the native snapshot'
    return {'source_outcome': 'UNDEFINED_ROTATION_AXIS', 'comparison_kind': POLICY,
            'policy_outcome': 'REJECTED', 'policy_error': ERROR,
            'numeric_source_match_claimed': False}
