#!/usr/bin/env python3
"""Known input-only IEEE reference witness; no product is executed."""
import json
from pathlib import Path
import numpy as np
from static_usd_runtime import source_f32_triangle_normals
r=json.loads((Path(__file__).resolve().parents[1]/'baseline/static-usd-normal-rule/triangle104.json').read_text())
actual=source_f32_triangle_normals([r['points']])[0]
assert np.array_equal(actual.view(np.uint32),np.asarray(r['f32_sequential_newell'],dtype=np.float32).view(np.uint32))
assert max(abs(float(x)-y) for x,y in zip(actual,r['f64_geometric_cross']))>r['continuous_tolerance']
assert r['continuous_tolerance']==1e-6
print(json.dumps({'passed':True,'rule':'input-only f32 sequential Newell','f64_difference_retained':r['difference_max'],'scope':'reference arithmetic only, not product performance'}))
