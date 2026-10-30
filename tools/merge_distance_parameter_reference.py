"""Derive fixed Python operator scalar conversion; read no source results."""
import math

from generate_merge_distance_cases import f32


TOKENS = {'nan': math.nan, 'positive_infinity': math.inf, 'negative_infinity': -math.inf}


def native_parameters(parameters):
    return {key: TOKENS[value['$native_float']] if type(value) is dict and set(value) == {'$native_float'} and
            value['$native_float'] in TOKENS else value for key, value in parameters.items()}


def recorded_parameters(parameters):
    return {key: {'$nonfinite': value['$native_float']} if type(value) is dict and set(value) == {'$native_float'} and
            value['$native_float'] in TOKENS else value for key, value in parameters.items()}


def converted(parameters):
    values = {'threshold': f32(1e-4), 'use_centroid': True, 'use_unselected': False, 'use_sharp_edge_from_normals': False}
    nonfinite = None
    for name in values:
        if name not in parameters: continue
        raw = parameters[name]
        if name == 'threshold':
            if type(raw) is dict and set(raw) == {'$native_float'} and raw['$native_float'] in TOKENS:
                nonfinite = raw['$native_float']
                values[name] = 50. if nonfinite == 'positive_infinity' else f32(1e-6)
                continue
            if type(raw) not in [float, int, bool]: return {'classification': 'rejected_no_operation', 'parameter': name}
            try: number = float(raw)
            except OverflowError: return {'classification': 'rejected_no_operation', 'parameter': name}
            assert math.isfinite(number), 'nonfinite scalar source probes need a separate classification'
            try: number = f32(number)
            except OverflowError: number = math.copysign(math.inf, number)
            values[name] = max(f32(1e-6), min(50., number))
        else:
            if type(raw) not in [int, bool] or raw not in [0, 1]:
                return {'classification': 'rejected_no_operation', 'parameter': name}
            values[name] = bool(raw)
    unknown = set(parameters)-set(values)
    if unknown: return {'classification': 'rejected_no_operation', 'parameter': sorted(unknown)[0]}
    if nonfinite:
        return {'classification': 'native_nonfinite_source_probe', 'native_token': nonfinite,
                'parameters': None if nonfinite == 'nan' else values, 'numeric_match_claimed': False}
    return {'classification': 'finished_numeric', 'parameters': values}
