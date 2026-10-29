#!/usr/bin/env python3
"""Prove the unwritten source axis without performing an uninitialized read."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BINARY = Path('/Applications/Blender.app/Contents/MacOS/Blender')
BINARY_SHA = 'de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def callback(text):
    start = text.index('static void constraints_rotation_impl(')
    brace = text.index('{', start)
    depth = 0
    for index in range(brace, len(text)):
        depth += (text[index] == '{') - (text[index] == '}')
        if depth == 0:
            return text[start:index+1]
    raise ValueError('unterminated source callback')


def capture(output):
    assert not output.exists(), 'refuse existing evidence'
    paths = [ROOT/'baseline/sources/undefined-rotation/transform.hh',
             ROOT/'baseline/sources/mesh-transform-core/transform_constraints.cc',
             ROOT/'baseline/sources/mesh-transform/transform_mode.cc',
             ROOT/'baseline/sources/mesh-transform/transform_mode_rotate.cc',
             ROOT/'docs/contracts/undefined-rotation-rejection.md', Path(__file__)]
    hashes = {str(p.relative_to(ROOT)):sha(p) for p in paths}
    header = paths[0].read_text()
    for index, name in enumerate(['CON_APPLY','CON_AXIS0','CON_AXIS1','CON_AXIS2']):
        assert f'{name} = 1 << {index},' in header
    body = callback(paths[1].read_text())
    prefix = '''#include <cassert>
#include <cstdio>
#define BLI_assert assert
enum { CON_APPLY=1<<0, CON_AXIS0=1<<1, CON_AXIS1=1<<2, CON_AXIS2=1<<3 };
struct TransInfo { struct { int mode; } con; };
static void copy_v3_v3(float *out,const float *in) { for(int i=0;i<3;++i) out[i]=in[i]; }
'''
    suffix = '''
int main() {
  const float basis[3][3]={{2,3,5},{7,11,13},{17,19,23}};
  for(int mask=0;mask<8;++mask) {
    TransInfo t{{CON_APPLY | (mask<<1)}};
    float axis[3]={41,-43,47};
    constraints_rotation_impl(&t,basis,axis);
    std::printf("{\\"mask\\":%d,\\"axis\\":[%.9g,%.9g,%.9g]}\\n",mask,axis[0],axis[1],axis[2]);
  }
}
'''
    assert sha(BINARY) == BINARY_SHA
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='formora-rotation-proof-',dir=output.parent) as temporary:
        folder = Path(temporary)/'evidence'
        folder.mkdir()
        (folder/'callback.cc').write_text(body+'\n')
        (folder/'driver.cc').write_text(prefix+body+suffix)
        command = ['xcrun','clang++','-std=c++17','-O2','-Wall','-Wextra','-Werror',
                   str(folder/'driver.cc'),'-o',str(folder/'probe')]
        compiled = subprocess.run(command,capture_output=True)
        (folder/'compile.stdout').write_bytes(compiled.stdout)
        (folder/'compile.stderr').write_bytes(compiled.stderr)
        compiled.check_returncode()
        native = subprocess.run([str(folder/'probe')],capture_output=True,check=True)
        (folder/'probe.stdout').write_bytes(native.stdout)
        (folder/'probe.stderr').write_bytes(native.stderr)
        rows = [json.loads(line) for line in native.stdout.splitlines()]
        assert len(rows)==8 and [r['mask'] for r in rows]==list(range(8))
        basis = [[2,3,5],[7,11,13],[17,19,23]]
        expected = {0:[41,-43,47],1:basis[0],2:basis[1],3:basis[2],
                    4:basis[2],5:basis[1],6:basis[0],7:[41,-43,47]}
        assert all(row['axis']==expected[row['mask']] for row in rows)
        symbols = subprocess.run(['xcrun','nm','-nm',str(BINARY)],capture_output=True,check=True)
        wanted = ['L13applyRotationEPNS1_9TransInfoE', 'transform_mode_rotation_axis_get',
                  'applyAxisConstraintRot','applyObjectConstraintRot']
        selected = []
        commands = []
        for index,name in enumerate(wanted):
            lines = [line for line in symbols.stdout.decode().splitlines() if name in line]
            assert len(lines)==1,(name,lines)
            selected.append(lines[0])
            start = int(lines[0].split()[0],16)
            stop = start + (128 if index==0 else 384)
            cmd = ['xcrun','llvm-objdump','-d',f'--start-address={start:#x}',
                   f'--stop-address={stop:#x}',str(BINARY)]
            data = subprocess.run(cmd,capture_output=True,check=True)
            (folder/f'native-{index}.stdout').write_bytes(data.stdout)
            (folder/f'native-{index}.stderr').write_bytes(data.stderr)
            commands.append(cmd)
        (folder/'native-symbols.txt').write_text('\n'.join(selected)+'\n')
        compiler = subprocess.run(['xcrun','clang++','--version'],capture_output=True,check=True)
        (folder/'compiler.txt').write_bytes(compiler.stdout+compiler.stderr)
        (folder/'capture-driver.py').write_bytes(Path(__file__).read_bytes())
        assert hashes=={str(p.relative_to(ROOT)):sha(p) for p in paths}
        assert sha(BINARY)==BINARY_SHA
        report = {'passed':True, 'source_commit':'e13b728c6880d3084d9d57c30031ed5df8b39dee',
                  'binary_sha256':BINARY_SHA,'input_hashes':hashes,'compile_command':command,
                  'disassembly_commands':commands,'callback_sha256':hashlib.sha256(body.encode()).hexdigest(),
                  'unmodified_callback_body':True,'probe_reads_uninitialized_memory':False,
                  'cases':rows,'all_three_axis_callback_writes_output':False,
                  'source_review':'Caller passes its uninitialized stack axis to the callback. The all-axis callback returns without storing to the output. Disassembly is retained for manual inspection.',
                  'operator_numeric_parity_claim':False,
                  'artifacts':{p.name:sha(p) for p in sorted(folder.iterdir()) if p.is_file()}}
        (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        folder.rename(output)
    print(json.dumps({'passed':True,'masks':8,'all_three_axis_callback_writes_output':False,
                      'probe_reads_uninitialized_memory':False}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    capture(parser.parse_args().output.resolve())
