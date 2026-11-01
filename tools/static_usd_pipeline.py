"""Complete concurrent pipeline; caller's wall clock encloses this whole call."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event


def execute(export, query, initialize, validate):
    errors=[]
    export_problem=None
    export_started=Event()
    query_started=Event()

    def prepare():
        assert export_started.wait(120),'native export start signal missing'
        return initialize()

    def compare():
        assert query_started.wait(120),'native query start signal missing'
        return validate()

    with ThreadPoolExecutor(max_workers=1,thread_name_prefix='formora-usd-pipeline') as pool:
        startup=pool.submit(prepare)
        validation=None
        try:
            receipt=export(export_started)
            assert export_started.is_set(),'native export start signal missing'
        except BaseException as problem:
            export_problem=problem
        finally:
            # Release the waiter even when Popen itself fails. An event does
            # not establish success; the original exception still fails.
            export_started.set()
        if export_problem is None:
            validation=pool.submit(compare)
            try:
                query(query_started)
                assert query_started.is_set(),'native query start signal missing'
            except BaseException as problem:
                errors.append({'stage':'query','error':repr(problem)})
            finally:
                query_started.set()
        for name,future in [('initialize',startup),('validate',validation)]:
            if future is None:
                continue
            try:
                future.result()
            except BaseException as problem:
                errors.append({'stage':name,'error':repr(problem)})
    # The executor has joined every worker before return or exception.
    if export_problem is not None:
        if errors:
            export_problem.add_note('Concurrent verifier failures: '+repr(errors))
        raise export_problem
    return receipt,errors
