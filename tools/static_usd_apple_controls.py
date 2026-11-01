#!/usr/bin/env python3
"""Actually load semantic corruptions in Apple, then require comparison failure."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from static_usd_apple_check import check

def remove_block(text,token):
    start=text.index(token);opening=text.index('{',start);depth=1;i=opening+1
    # This control edits only the canonical gate's ASCII hex paths and simple
    # names; it is not a general USD parser and is never used for product export.
    while depth:
        depth+=(text[i]=='{')-(text[i]=='}');i+=1
    return text[:start]+text[i:],text[start:i]

def run(inspector,mother,usd,output):
    output.mkdir(parents=True,exist_ok=False);scene=json.loads(mother.read_text());original=usd.read_text();records=[]
    for kind in ('axis','unit','material','geometry','hierarchy'):
        if kind=='axis':text=original.replace('upAxis = "Z"','upAxis = "Y"',1)
        elif kind=='unit':text=original.replace('metersPerUnit = 1','metersPerUnit = 0.01',1)
        elif kind=='material':text=re.sub(r'float inputs:roughness = [^\n]+','float inputs:roughness = 0.123',original,count=1)
        elif kind=='geometry':text,_=remove_block(original,'def Mesh "Geometry"')
        else:
            child=next(k for k,e in scene['entities'].items() if e['parent']=='crate')
            text,block=remove_block(original,'def Xform "id_'+child.encode().hex()+'"')
            text=text.replace('def Scope "Materials"',block+'\ndef Scope "Materials"',1)
        assert text!=original
        folder=output/kind;folder.mkdir();source=folder/'wrong.usda';source.write_text(text)
        report=folder/'loaded.json';args=[str(inspector),str(source),str(report)];start=time.monotonic_ns()
        with (folder/'stdout.txt').open('w') as stdout,(folder/'stderr.txt').open('w') as stderr:
            process=subprocess.Popen(args,stdout=stdout,stderr=stderr);code=process.wait(timeout=30)
        record={'kind':kind,'command':args,'pid':process.pid,'waited':True,'exit_code':code,'elapsed_ns':time.monotonic_ns()-start,'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'binary_sha256':hashlib.sha256(inspector.read_bytes()).hexdigest()}
        (folder/'process.json').write_text(json.dumps(record,indent=2)+'\n')
        assert code==0,'Corruption must remain loadable; loader failure alone does not prove semantic detection'
        actual=json.loads(report.read_text())
        try:check(actual,scene,'crate')
        except (AssertionError,KeyError,StopIteration) as problem:record['comparison_error']=str(problem) or type(problem).__name__;record['detected']=True
        else:raise AssertionError('Missed Apple corruption '+kind)
        records.append(record);(output/'report.json').write_text(json.dumps({'passed':len(records)==5,'controls':records},indent=2)+'\n')
        print(json.dumps({'kind':kind,'exit_code':code,'detected':True,'error':record['comparison_error']}),flush=True)
if __name__=='__main__':run(*(Path(x).resolve() for x in sys.argv[1:5]))
