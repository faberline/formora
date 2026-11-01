#!/usr/bin/env python3
"""Eight actual Formora GPU renders. Uses CI-authored mother files unchanged."""
import hashlib
import json
import math
from pathlib import Path
import sys
from static_usd_runtime import Runner, load, sha

DIRECTIONS=[[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1],[1,-1,0.7],[-1,1,0.6]]
def unit(v):
    n=math.sqrt(sum(x*x for x in v));return [x/n for x in v]
def cross(a,b):return [a[(i+1)%3]*b[(i+2)%3]-a[(i+2)%3]*b[(i+1)%3] for i in range(3)]
def quaternion(rows):
    m=rows;t=sum(m[i][i] for i in range(3))
    if t>0:
        s=math.sqrt(t+1)*2;q=[(m[2][1]-m[1][2])/s,(m[0][2]-m[2][0])/s,(m[1][0]-m[0][1])/s,s/4]
    else:
        i=max(range(3),key=lambda i:m[i][i]);j=(i+1)%3;k=(i+2)%3;s=math.sqrt(1+m[i][i]-m[j][j]-m[k][k])*2
        q=[0.,0.,0.,0.];q[i]=s/4;q[j]=(m[j][i]+m[i][j])/s;q[k]=(m[k][i]+m[i][k])/s;q[3]=(m[k][j]-m[j][k])/s
    return unit(q)

def run(binary,mother,output):
    original=mother.read_bytes();scene=load(mother);output.mkdir(parents=True,exist_ok=False);runner=Runner(output)
    points=[]
    for e in scene['entities'].values():
        if e['content']['kind']!='mesh':continue
        t=e['transform']['translation'];points += [[x+y for x,y in zip(v,t)] for v in scene['mesh_assets'][e['content']['geometry']['id']]['vertices'].values()]
    lo=[min(p[i] for p in points) for i in range(3)];hi=[max(p[i] for p in points) for i in range(3)];center=[(a+b)/2 for a,b in zip(lo,hi)];radius=math.sqrt(sum((b-a)**2 for a,b in zip(lo,hi)))*1.8
    records=[]
    for i,direction in enumerate(DIRECTIONS):
        z=unit(direction);up=[0,1,0] if abs(z[2])>.99 else [0,0,1];x=unit(cross(up,z));y=cross(z,x)
        transform={'translation':[a+b*radius for a,b in zip(center,z)],'rotation':quaternion([[x[j],y[j],z[j]] for j in range(3)]),'scale':[1,1,1]}
        copy=json.loads(original);copy['entities']['preview_camera']={'name':'preview_camera','parent':None,'transform':transform,'content':{'kind':'camera','vertical_fov_degrees':45,'near':.01,'far':100}}
        for label,offset,intensity in [('key',[1,-1,1.5],350),('fill',[-1,0.7,-0.8],170)]:
            copy['entities']['preview_'+label]={'name':'preview_'+label,'parent':None,'transform':{'translation':[a+b*radius for a,b in zip(center,offset)],'rotation':[0,0,0,1],'scale':[1,1,1]},'content':{'kind':'light','color':[1,1,1],'intensity':intensity}}
        copy['active_camera']='preview_camera';camera=output/f'camera-{i:02}.json';camera.write_text(json.dumps(copy,indent=2)+'\n')
        png=output/f'view-{i:02}.png'
        receipt=runner.run([binary,'render','--scene',camera,'--output',png,'--width','800','--height','800'])
        records.append({'camera':str(camera),'camera_sha256':sha(camera),'transform':transform,'png':str(png),'png_sha256':sha(png),'gpu':receipt['gpu']})
    assert original==mother.read_bytes()
    (output/'manifest.json').write_text(json.dumps({'mother_sha256':sha(mother),'binary_sha256':sha(binary),'views':records,'image_quality_review':'pending','passed':False},indent=2)+'\n')
if __name__=='__main__':run(Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve(),Path(sys.argv[3]).resolve())
