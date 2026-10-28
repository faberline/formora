import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('source_collection', ROOT/'tools/collect_baseline.py')
collection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collection)
BASE = collection.UNREAL
START = collection.pin_unreal(BASE+'/unreal-engine-5-8-documentation')


def url(name):
    return collection.pin_unreal(BASE+'/'+name)


def document(address, children=()):
    return {'url': address, 'title': address.split('/')[-1], 'document_id': 1,
            'revision_id': 2, 'applications': [{'version': '5.8'}],
            'response_sha256': 'a'*64,
            'children': [{'title': child.split('/')[-1], 'url': child} for child in children]}


def quiet(*_args, **_kwargs):
    pass


class CollectionTests(unittest.TestCase):
    def test_frozen_checkpoints_bind_the_seed_chain_and_keep_unique_documents(self):
        source_dir = ROOT/'baseline/sources'
        previous = source_dir/'unreal-5.8-documents-depth2-seed.json'
        seed, _digest = collection.load_unreal_seed(previous)
        self.assertEqual(len(seed), 362)
        raw_path = source_dir/'unreal-5.8-documents-depth2-raw.json'
        audit = json.loads(previous.read_text(encoding='utf-8'))['deduplication']
        self.assertEqual(audit['raw_capture_sha256'], hashlib.sha256(raw_path.read_bytes()).hexdigest())
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            collection.load_unreal_seed(raw_path)
        for depth in [3, 4, 5]:
            current = source_dir/f'unreal-5.8-documents-depth{depth}.json'
            capture = json.loads(current.read_text(encoding='utf-8'))
            self.assertEqual(capture['seed_sha256'], hashlib.sha256(previous.read_bytes()).hexdigest())
            loaded, _digest = collection.load_unreal_seed(current)
            self.assertEqual(len(loaded), len(capture['documents']))
            self.assertFalse(capture['traversal_complete'])
            previous = current
        self.assertEqual(len(capture['documents']), 1173)
        self.assertEqual(len(capture['failures']), 9)
        self.assertEqual(capture['frontier'], [])

    def test_rate_limit_cooldown_is_shared_with_the_next_request(self):
        now = [100.0]
        request_times = []
        def open_url(*_args, **_kwargs):
            request_times.append(now[0])
            if len(request_times) == 1:
                raise HTTPError(START, 429, 'rate limited', {'Retry-After': '17'}, None)
            return io.BytesIO(b'reference')
        def sleep(seconds):
            now[0] += seconds
        with patch.object(collection, '_next_request', 0.0), \
             patch.object(collection.time, 'monotonic', lambda: now[0]), \
             patch.object(collection.time, 'sleep', sleep), \
             patch.object(collection.urllib.request, 'urlopen', open_url):
            with self.assertRaises(HTTPError):
                collection.fetch(START)
            self.assertEqual(collection.fetch(START), b'reference')
        self.assertEqual(request_times, [100.0, 117.0])

    def test_shared_child_is_fetched_only_once(self):
        graph = {START: document(START, [url('a'), url('b')]),
                 url('a'): document(url('a'), [url('shared')]),
                 url('b'): document(url('b'), [url('shared')]),
                 url('shared'): document(url('shared'))}
        calls = []
        def retrieve(address):
            calls.append(address)
            return graph[address]
        result, sources = collection.collect_unreal(2, retrieve=retrieve, progress=quiet)
        self.assertEqual(calls.count(url('shared')), 1)
        self.assertEqual(len(result['documents']), 4)
        self.assertEqual(set(sources), set(graph))
        self.assertTrue(result['traversal_complete'])

    def test_seed_reuse_keeps_the_same_frontier_and_sources(self):
        graph = {START: document(START, [url('a')]),
                 url('a'): document(url('a'), [url('b')]),
                 url('b'): document(url('b'))}
        fresh, fresh_sources = collection.collect_unreal(1, retrieve=graph.__getitem__, progress=quiet)
        calls = []
        def retrieve(address):
            calls.append(address)
            return graph[address]
        result, sources = collection.collect_unreal(1, {START: graph[START]}, retrieve, quiet)
        self.assertEqual(calls, [url('a')])
        self.assertEqual(result['documents_reused'], 1)
        self.assertEqual(result['documents'], fresh['documents'])
        self.assertEqual(result['frontier'], fresh['frontier'])
        self.assertEqual(result['frontier'], [{'title': 'b?application_version=5.8', 'url': url('b')}])
        self.assertEqual(sources, fresh_sources)
        self.assertFalse(result['traversal_complete'])

    def test_failed_seed_frontier_is_retried_without_dropping_its_source(self):
        root = document(START, [url('failed')])
        calls = []
        def retrieve(address):
            calls.append(address)
            raise OSError('reference unavailable')
        result, sources = collection.collect_unreal(2, {START: root}, retrieve, quiet)
        self.assertEqual(calls, [url('failed')])
        self.assertIn(url('failed'), sources)
        self.assertEqual(result['failures'], [{'url': url('failed'), 'error': 'reference unavailable'}])
        self.assertFalse(result['traversal_complete'])

    def test_cycle_does_not_create_a_false_unfetched_frontier(self):
        graph = {START: document(START, [url('a')]), url('a'): document(url('a'), [START])}
        result, _sources = collection.collect_unreal(1, retrieve=graph.__getitem__, progress=quiet)
        self.assertTrue(result['traversal_complete'])
        self.assertEqual(result['frontier'], [])

    def seed(self, docs):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'seed.json'
            path.write_text(json.dumps({'schema_version': 1, 'requested_version': '5.8', 'documents': docs}))
            return collection.load_unreal_seed(path)

    def test_seed_rejects_duplicate_urls_and_wrong_versions(self):
        source = document(START)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.seed([source, copy.deepcopy(source)])
        changed = copy.deepcopy(source)
        changed['applications'] = [{'version': '5.7'}]
        with self.assertRaisesRegex(ValueError, '5.8'):
            self.seed([changed])
        changed = copy.deepcopy(source)
        changed['url'] = START.replace('5.8', '5.7')
        with self.assertRaisesRegex(ValueError, 'canonical pinned'):
            self.seed([changed])

    def test_seed_rejects_invalid_digests_and_unpinned_children(self):
        changed = document(START)
        changed['response_sha256'] = 'not-a-digest'
        with self.assertRaisesRegex(ValueError, 'digest'):
            self.seed([changed])
        changed = document(START, [BASE+'/unversioned'])
        with self.assertRaisesRegex(ValueError, 'child URL'):
            self.seed([changed])

    def test_seed_load_binds_the_original_capture_bytes(self):
        source = document(START)
        result, digest = self.seed([source])
        self.assertEqual(result, {START: source})
        self.assertEqual(len(digest), 64)


if __name__ == '__main__':
    unittest.main()
