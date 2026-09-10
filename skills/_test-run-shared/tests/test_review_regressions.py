"""Regression cases found by the new-skill and script code review."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_test_run as fixtures
from test_run import ContractError, digest, load, pointer, record, write_new
from verify_defect import verify


class ReviewRegressions(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.RunTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def api_fixture(self):
        scope = self.f.scope
        scope['sources'][0]['kind'] = 'runner-definition'
        scope['targets'][0]['url'] = 'https://api.example.invalid'
        scope['checks'][0]['binding'] = {'runner': 'schemathesis', 'selector': 'suite', 'definition_source_id': 'source'}
        directory = self.f.frozen()
        draft = self.f.attempt(directory)
        attempt = load(draft)
        raw_path = self.f.root / attempt['evidence'][0]['path']
        metadata = {'started_at': attempt['started_at'], 'finished_at': attempt['finished_at'],
                    'definition_sha256': digest(self.f.root / 'check.json'), 'inputs_unchanged': True,
                    'input_sha256': [digest(self.f.root / 'check.json')],
                    'target_url': scope['targets'][0]['url']}
        raw = {'schema_version': 1, 'runner': 'schemathesis', 'status': 'passed', 'returncode': 0,
               'started_at': metadata['started_at'], 'finished_at': metadata['finished_at'], 'execution': metadata}
        return directory, draft, raw_path, raw

    def test_matching_native_provenance_passes(self):
        directory, draft, path, raw = self.api_fixture()
        path.write_text(json.dumps(raw))
        record(draft, self.f.root, directory)
        self.assertEqual(self.f.result(directory)['acceptance_status'], 'passed')

    def test_missing_provenance_is_inconclusive_not_native_failure(self):
        directory, draft, path, raw = self.api_fixture()
        del raw['execution']
        path.write_text(json.dumps(raw))
        attempt = record(draft, self.f.root, directory)
        self.assertEqual(attempt['status'], 'passed')
        self.assertEqual(self.f.result(directory)['acceptance_status'], 'inconclusive')

    def test_old_time_different_definition_and_target_are_rejected(self):
        directory, draft, path, raw = self.api_fixture()
        raw['execution'].update(started_at='2000-01-01T00:00:00Z', definition_sha256='0'*64, target_url='https://wrong.example.invalid')
        path.write_text(json.dumps(raw))
        record(draft, self.f.root, directory)
        result = self.f.result(directory)
        self.assertEqual(result['acceptance_status'], 'inconclusive')
        self.assertGreaterEqual(len(result['checks']['check']['reasons']), 3)

    def test_inputs_changed_during_runner_cannot_pass(self):
        directory, draft, path, raw = self.api_fixture()
        raw['execution']['inputs_unchanged'] = False
        path.write_text(json.dumps(raw))
        record(draft, self.f.root, directory)
        self.assertEqual(self.f.result(directory)['acceptance_status'], 'inconclusive')

    def test_unfrozen_auxiliary_schema_cannot_pass(self):
        directory, draft, path, raw = self.api_fixture()
        raw['execution']['input_sha256'].append('0'*64)
        path.write_text(json.dumps(raw))
        record(draft, self.f.root, directory)
        self.assertEqual(self.f.result(directory)['acceptance_status'], 'inconclusive')

    def defect_fixture(self, *, swap=False, green_status='passed', changed_tested_build=True):
        phases = {}
        for phase, status in [('red', 'failed'), ('green', green_status), ('regression', 'passed')]:
            build = 'old' if phase == 'red' else 'new'
            targets = [{'id':'web','platform':'web','build':build if changed_tested_build else 'old','environment':'test'},
                       {'id':'android','platform':'android','build':build,'environment':'test'}]
            self.f.scope['targets'] = targets
            target_id = 'android' if swap and phase != 'red' else 'web'
            self.f.scope['checks'][0]['target_id'] = target_id
            self.f.scope['capabilities'][0]['target_id'] = target_id
            directory = self.f.frozen(phase)
            draft_path = self.f.attempt(directory, status, signature='synthetic-bug')
            draft = load(draft_path)
            draft['target'] = next(t for t in targets if t['id']==target_id)
            draft_path.write_text(json.dumps(draft))
            record(draft_path, self.f.root, directory)
            phases[phase] = phase
        return {'schema_version':1,'defect_id':'BUG-001','expected':'confirmed','failure_signature':'synthetic-bug','conditions':'conditions.json','phases':phases}

    def test_cross_target_repair_rejected(self):
        defect = self.defect_fixture(swap=True)
        with self.assertRaises(ContractError):
            verify(self.f.root, defect)

    def test_unrelated_target_build_change_is_not_a_fix(self):
        defect = self.defect_fixture(changed_tested_build=False)
        with self.assertRaises(ContractError):
            verify(self.f.root, defect)

    def test_failed_green_is_failed(self):
        defect = self.defect_fixture(green_status='failed')
        self.assertEqual(verify(self.f.root, defect)['status'], 'failed')

    def test_reusing_green_as_regression_rejected(self):
        defect = self.defect_fixture()
        defect['phases']['regression'] = 'green'
        with self.assertRaises(ContractError):
            verify(self.f.root, defect)

    def test_pointer_negative_or_noncanonical_index_rejected(self):
        for locator in ('/-1', '/01', '/+0', '/2', '/~2'):
            with self.subTest(locator=locator), self.assertRaises(ContractError):
                pointer([{'status':'failed'}, {'status':'passed'}], locator)
        self.assertEqual(pointer({'a/b': {'~key': 1}}, '/a~1b/~0key'), 1)

    def test_nonfinite_json_and_partial_write_rejected(self):
        path = self.f.root / 'invalid.json'
        path.write_text('{"value":NaN}')
        with self.assertRaises(ContractError):
            load(path)
        output = self.f.root / 'output.json'
        with self.assertRaises(ValueError):
            write_new(output, {'bad':float('nan')})
        self.assertFalse(output.exists())

    def test_attempt_output_symlink_escape_rejected(self):
        directory = self.f.frozen()
        with tempfile.TemporaryDirectory() as external:
            (directory / 'attempts').symlink_to(external, target_is_directory=True)
            with self.assertRaises(ContractError):
                record(self.f.attempt(directory), self.f.root, directory)
            self.assertEqual(list(Path(external).iterdir()), [])

    def test_supplied_scope_hash_is_not_silently_replaced(self):
        directory = self.f.frozen()
        path = self.f.attempt(directory)
        value = load(path)
        value['scope_sha256'] = '0'*64
        path.write_text(json.dumps(value))
        with self.assertRaises(ContractError):
            record(path, self.f.root, directory)

    def test_deep_acyclic_plan_does_not_overflow_stack(self):
        base = self.f.scope['checks'][0]
        self.f.scope['checks'] = [{**copy.deepcopy(base), 'id':f'check-{i}', 'depends_on':[f'check-{i-1}'] if i else []} for i in range(1100)]
        self.f.frozen()


if __name__ == '__main__':
    unittest.main()
