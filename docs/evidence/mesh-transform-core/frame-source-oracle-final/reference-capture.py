import bpy, json, math
from mathutils import Matrix,Vector
from pathlib import Path
output=Path('/private/tmp/formora-world-frame-reference');output.mkdir(exist_ok=True)
cases=[]
for index,order in enumerate(['XYZ','XZY','YXZ','YZX','ZXY','ZYX']):
 parent=bpy.data.objects.new('parent-'+order,None);bpy.context.collection.objects.link(parent)
 parent.location=(1.25,-0.75,2);parent.rotation_mode=order;parent.rotation_euler=(0.37,-0.23,0.51);parent.scale=(1.2,0.7,1.6)
 child=bpy.data.objects.new('child-'+order,None);bpy.context.collection.objects.link(child);child.parent=parent;child.matrix_parent_inverse=Matrix.Identity(4)
 child.location=(-0.7,0.35,0.6);child.rotation_mode=order;child.rotation_euler=(0.13,0.29,-0.41);child.scale=(0.9,1.4,0.8)
 bpy.context.view_layer.update()
 def values(obj):return {'location':list(obj.location),'angles':list(obj.rotation_euler),'order':obj.rotation_mode,'scale':list(obj.scale),'local_matrix':[list(row) for row in obj.matrix_basis],'world_matrix':[list(row) for row in obj.matrix_world]}
 cases.append({'id':order,'parent':values(parent),'child':values(child),'point':[3.25,-1.7,0.9],'world_point':list(child.matrix_world@Vector((3.25,-1.7,0.9)))})
a=Matrix(((2e10,1,-2e10,1),(0,1,0,0),(0,0,1,0),(0,0,0,1)));b=Matrix(((1,0,0,0),(1,1,0,0),(1,0,1,0),(1,0,0,1)))
report={'version':bpy.app.version_string,'build_hash':bpy.app.build_hash.decode(),'matrix_product_probe':{'a':[list(r) for r in a],'b':[list(r) for r in b],'result':[list(r) for r in a@b]},'cases':cases}
(output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'cases':len(cases),'balanced_product_first':report['matrix_product_probe']['result'][0][0]}))
