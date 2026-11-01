#!/usr/bin/env python3
"""Independent frozen full-value/type/float-bit equivalence. CI only."""
import json
from pathlib import Path
import struct
import orjson

assert orjson.__version__=='3.13.0'
reference=json.loads((Path(__file__).resolve().parents[1]/'baseline/static-usd-verifier-json/reference.json').read_text())
def same(actual,expected):
    assert type(actual) is type(expected),(type(actual),type(expected))
    if isinstance(expected,dict):
        assert actual.keys()==expected.keys()
        for key in expected:same(actual[key],expected[key])
    elif isinstance(expected,list):
        assert len(actual)==len(expected)
        for a,e in zip(actual,expected):same(a,e)
    elif isinstance(expected,float):assert struct.pack('>d',actual)==struct.pack('>d',expected),(actual,expected)
    else:assert actual==expected,(actual,expected)
for text in reference['valid']:same(orjson.loads(text.encode('utf-8')),json.loads(text))
for raw in [*(s.encode('utf-8') for s in reference['invalid']),b'"\xff"']:
    try:orjson.loads(raw)
    except orjson.JSONDecodeError:pass
    else:raise AssertionError(('accepted invalid JSON',raw))
print(json.dumps({'passed':True,'valid_full_value_type_and_f64_bit_cases':len(reference['valid']),'invalid_rejected':len(reference['invalid'])+1,'scope':'verifier decoder equivalence only, not product acceptance'}))
