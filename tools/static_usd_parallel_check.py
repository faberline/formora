"""Independent frozen ordering/failure controls. Helper only; CI only."""
import json
from pathlib import Path
from threading import Event,enumerate as threads
from static_usd_pipeline import execute

reference=json.loads((Path(__file__).resolve().parents[1]/'baseline/static-usd-parallel-contract.json').read_text())
checked=[]
def joined():
    assert not any(t.name.startswith('formora-usd-pipeline') for t in threads())
def export(started):
    started.set()
    return {'exported':True}
def query(started):
    started.set()
def nothing():
    return None

# Initialization must wait for native spawn; export must overlap initialization.
native_began=Event(); initialized=Event(); query_began=Event()
validation_began=Event(); query_done=Event(); validation_done=Event()
def first_export(started):
    native_began.set();started.set()
    assert initialized.wait(5)
    return {'exported':True}
def initialize():
    assert native_began.is_set()
    initialized.set()
def first_query(started):
    query_began.set();started.set()
    assert validation_began.wait(5)
    query_done.set()
def first_validation():
    assert query_began.is_set()
    validation_began.set()
    assert query_done.wait(5)
    validation_done.set()
receipt,errors=execute(first_export,first_query,initialize,first_validation)
assert receipt=={'exported':True} and not errors
assert query_done.is_set() and validation_done.is_set()
joined();checked.extend(reference['independent_control_cases'][:2])

validation_finished=Event()
def broken_query(started):
    started.set()
    raise ValueError('independent-query-failure')
_,errors=execute(export,broken_query,nothing,validation_finished.set)
assert errors==[{'stage':'query','error':"ValueError('independent-query-failure')"}]
assert validation_finished.is_set();joined();checked.append(reference['independent_control_cases'][2])

query_finished=Event()
def good_query(started):
    started.set();query_finished.set()
def broken_validation():
    raise ValueError('independent-validation-failure')
_,errors=execute(export,good_query,nothing,broken_validation)
assert errors==[{'stage':'validate','error':"ValueError('independent-validation-failure')"}]
assert query_finished.is_set();joined();checked.append(reference['independent_control_cases'][3])

def broken_initialize():
    raise RuntimeError('independent-initialization-failure')
_,errors=execute(export,query,broken_initialize,nothing)
assert errors==[{'stage':'initialize','error':"RuntimeError('independent-initialization-failure')"}]
joined();checked.append(reference['independent_control_cases'][4])

waiter_finished=Event()
def broken_export(started):
    raise OSError('independent-native-launch-failure')
try:execute(broken_export,query,waiter_finished.set,nothing)
except OSError as error:assert str(error)=='independent-native-launch-failure'
else:raise AssertionError('accepted launch failure')
assert waiter_finished.is_set();joined();checked.append(reference['independent_control_cases'][5])

waiter_finished.clear()
try:execute(lambda started:{'exported':True},query,waiter_finished.set,nothing)
except AssertionError as error:assert str(error)=='native export start signal missing'
else:raise AssertionError('accepted missing native start')
assert waiter_finished.is_set();joined();checked.append(reference['independent_control_cases'][6])
assert checked==reference['independent_control_cases']

# Preserve both independent failures when launch and initialization fail together.
try:execute(broken_export,query,broken_initialize,nothing)
except OSError as error:
    assert str(error)=='independent-native-launch-failure'
    assert len(error.__notes__)==1 and 'independent-initialization-failure' in error.__notes__[0]
else:raise AssertionError('accepted simultaneous failures')
joined()
_,errors=execute(export,lambda started:None,nothing,nothing)
assert len(errors)==1 and errors[0]['stage']=='query' and 'native query start signal missing' in errors[0]['error']
joined()
print(json.dumps({'passed':True,'controls':checked,'additional_controls':['retain simultaneous launch/init failures','reject missing query-start signal'],'scope':'complete wait/error helper only; no product or timing acceptance'}))
