"""Synthetic artifact/recording checks. No load tool or network is used."""
import copy
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
from eval_artifacts import validate, digest


def module(path):
    spec = importlib.util.spec_from_file_location('test_run_perfspec', path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='perfspec-contract-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        shutil.copytree(ROOT/'examples/synthetic-perfspec', self.root, dirs_exist_ok=True)
        self.result_path = self.root/'test-runs/catalog-load/performance-result.json'

    def mutate_result(self, mutation):
        value=json.loads(self.result_path.read_text())
        mutation(value)
        self.result_path.write_text(json.dumps(value))

    def rebind_inputs(self):
        plan_path=self.root/'perfspec/catalog/plan.json'
        scope_path=self.root/'test-runs/catalog-load/scope.json'
        execution_path=self.root/'test-runs/catalog-load/execution.json'
        scope=json.loads(scope_path.read_text())
        for source in scope['sources']:
            source['sha256']=digest(self.root/source['path'])
        scope_path.write_text(json.dumps(scope))
        execution=json.loads(execution_path.read_text())
        for key in ('input_hashes_before','input_hashes_after'):
            execution[key]={source['path']:source['sha256'] for source in scope['sources']}
        execution['scope_sha256']=digest(scope_path)
        execution_path.write_text(json.dumps(execution))
        result=json.loads(self.result_path.read_text())
        result['plan_sha256']=digest(plan_path)
        result['scope']['sha256']=digest(scope_path)
        result['execution']['sha256']=digest(execution_path)
        self.result_path.write_text(json.dumps(result))

    def test_complete_synthetic_artifacts_and_history(self):
        for stage in ('analysis', 'plan', 'generate', 'evaluate'):
            validate(self.root, stage)
        validate(self.root, 'evaluate', run='history')

    def test_decision_only_cannot_replace_formal_output(self):
        self.result_path.unlink()
        (self.root/'eval-result.json').write_text('{"verdict":"passed"}')
        with self.assertRaises(AssertionError):
            validate(self.root, 'evaluate')

    def test_missing_native_asset_and_required_mapping(self):
        manifest=self.root/'perfspec/catalog/asset-manifest.json'
        original=manifest.read_text()
        value=json.loads(original); value['mappings']=[]
        manifest.write_text(json.dumps(value))
        with self.assertRaisesRegex(AssertionError, 'mapping'):
            validate(self.root, 'generate')
        manifest.write_text(original)
        (self.root/'perfspec/catalog/assets/k6/catalog.js').unlink()
        with self.assertRaises(AssertionError):
            validate(self.root, 'generate')

    def test_wrong_hash_and_missing_scenario(self):
        original=self.result_path.read_text()
        self.mutate_result(lambda r:r.update(plan_sha256='0'*64))
        with self.assertRaises(AssertionError):validate(self.root,'evaluate')
        self.result_path.write_text(original)
        self.mutate_result(lambda r:r.update(scenarios=[]))
        with self.assertRaises(AssertionError):validate(self.root,'evaluate')

    def test_array_checks_and_key_mismatch(self):
        original=self.result_path.read_text()
        self.mutate_result(lambda r:r.update(checks=list(r['checks'].values())))
        with self.assertRaises(AssertionError):validate(self.root,'evaluate')
        self.result_path.write_text(original)
        self.mutate_result(lambda r:r['checks']['PERF_SLA'].update(id='other'))
        with self.assertRaises(AssertionError):validate(self.root,'evaluate')

    def test_false_pass_with_unknown_cleanup_rejected(self):
        self.mutate_result(lambda r:r.update(cleanup_status='unknown'))
        with self.assertRaises(AssertionError):validate(self.root,'evaluate')

    def test_required_scope_cannot_be_downgraded(self):
        self.mutate_result(lambda r:r['scenarios'][0].update(required=False, observed=False, metrics=[], threshold_results=[]))
        with self.assertRaisesRegex(AssertionError, 'required differs'):
            validate(self.root, 'evaluate')

    def test_threshold_ids_cannot_be_removed_replaced_or_duplicated(self):
        # Two planned thresholds prove that a nonempty subset is insufficient.
        plan_path = self.root/'perfspec/catalog/plan.json'
        plan = json.loads(plan_path.read_text())
        second = copy.deepcopy(plan['scenarios'][0]['thresholds'][0])
        second.update(id='PERF_P99', statistic='p99', value=800)
        plan['scenarios'][0]['thresholds'].append(second)
        plan_path.write_text(json.dumps(plan))
        execution_path = self.root/'test-runs/catalog-load/execution.json'
        execution = json.loads(execution_path.read_text())
        for key in ('input_hashes_before', 'input_hashes_after'):
            execution[key]['perfspec/catalog/plan.json'] = digest(plan_path)
        execution_path.write_text(json.dumps(execution))
        result = json.loads(self.result_path.read_text())
        result['plan_sha256'] = digest(plan_path)
        result['execution']['sha256'] = digest(execution_path)
        second_result = copy.deepcopy(result['scenarios'][0]['threshold_results'][0])
        second_result.update(id='PERF_P99', limit=800)
        result['scenarios'][0]['threshold_results'].append(second_result)
        metric=copy.deepcopy(result['scenarios'][0]['metrics'][0]);metric['statistic']='p99'
        result['scenarios'][0]['metrics'].append(metric)
        self.result_path.write_text(json.dumps(result))
        self.rebind_inputs()
        validate(self.root, 'evaluate')
        original = self.result_path.read_text()
        for change in ('remove', 'replace', 'duplicate'):
            with self.subTest(change=change):
                self.result_path.write_text(original)
                def mutate(r):
                    thresholds = r['scenarios'][0]['threshold_results']
                    if change == 'remove': thresholds.pop()
                    elif change == 'replace': thresholds[0]['id'] = 'invented'
                    else: thresholds.append(copy.deepcopy(thresholds[0]))
                self.mutate_result(mutate)
                with self.assertRaisesRegex(AssertionError, 'threshold coverage'):
                    validate(self.root, 'evaluate')

    def test_ready_plan_requires_covered_executable_load_and_window(self):
        path = self.root/'perfspec/catalog/plan.json'
        original = json.loads(path.read_text())
        changes = {
            'empty profiles': lambda p:p.update(profiles=[]),
            'missing required coverage': lambda p:p['profiles'][0].update(scenario_ids=[]),
            'empty stages': lambda p:p['profiles'][0]['load'].update(stages=[]),
            'zero duration': lambda p:p['profiles'][0]['load']['stages'][0].update(duration_seconds=0),
            'negative load': lambda p:p['profiles'][0]['load']['stages'][0].update(target=-1),
            'no load': lambda p:p['profiles'][0]['load']['stages'][0].update(target=0),
            'bool duration': lambda p:p['profiles'][0]['load']['stages'][0].update(duration_seconds=True),
            'missing phase': lambda p:p['profiles'][0]['measurement'].update(phase='absent'),
            'zero window': lambda p:p['profiles'][0]['measurement'].update(duration_seconds=0),
            'long window': lambda p:p['profiles'][0]['measurement'].update(duration_seconds=61),
            'long phases': lambda p:p['profiles'][0]['phases'][0].update(duration_seconds=61),
        }
        for name, mutation in changes.items():
            with self.subTest(name=name):
                value = copy.deepcopy(original); mutation(value)
                path.write_text(json.dumps(value))
                with self.assertRaises(AssertionError):validate(self.root, 'plan')
        # An unfinished draft remains a valid planning output, never generation-ready.
        draft = copy.deepcopy(original)
        draft.update(status='draft', profiles=[], blockers=['load not yet decided'])
        path.write_text(json.dumps(draft))
        validate(self.root, 'plan')
        with self.assertRaises(AssertionError):validate(self.root, 'generate')
        # A zero-load cooldown after a real measured phase is legitimate.
        original['profiles'][0]['load']['stages'].append({'duration_seconds':10, 'target':0})
        original['profiles'][0]['phases'].append({'name':'cooldown', 'duration_seconds':10})
        path.write_text(json.dumps(original))
        validate(self.root, 'plan')
        original['profiles'][0]['measurement'].update(phase='cooldown', duration_seconds=10)
        path.write_text(json.dumps(original))
        with self.assertRaisesRegex(AssertionError, 'no positive load'):
            validate(self.root, 'plan')

    def test_optional_profile_cannot_replace_required_coverage(self):
        path = self.root/'perfspec/catalog/plan.json'
        plan = json.loads(path.read_text())
        optional=copy.deepcopy(plan['scenarios'][0])
        optional.update(id='optional', required=False, exclusion_reason='optional exploration')
        plan['scenarios'].append(optional)
        plan['profiles'][0]['scenario_ids']=['optional']
        path.write_text(json.dumps(plan))
        with self.assertRaisesRegex(AssertionError, 'required scenario missing'):
            validate(self.root, 'plan')

    def test_required_observation_and_metrics_cannot_be_empty(self):
        original = self.result_path.read_text()
        for key, value in [('observed',False), ('metrics',[])]:
            with self.subTest(key=key):
                self.result_path.write_text(original)
                self.mutate_result(lambda r:r['scenarios'][0].update({key:value}))
                with self.assertRaisesRegex(AssertionError, 'unobserved or missing metrics'):
                    validate(self.root, 'evaluate')

    def test_unbound_report_cannot_invent_identity(self):
        path = self.root/'history/performance-result.json'
        original = json.loads(path.read_text())
        changes = {
            'spec_id':'fake', 'run_id':'fake', 'plan_sha256':'0'*64,
            'target':{'build':'invented'},
            'execution':{'path':'missing-execution.json', 'sha256':'0'*64},
            'window':{'started_at':'invented'},
            'runner':{'name':'k6', 'version':'invented'},
        }
        for key, value in changes.items():
            with self.subTest(key=key):
                changed=copy.deepcopy(original); changed[key]=value
                path.write_text(json.dumps(changed))
                with self.assertRaises(AssertionError):
                    validate(self.root, 'evaluate', run='history', unbound_report_only=True)
                with self.assertRaises(AssertionError):
                    validate(self.root, 'evaluate', run='history')
        # A runner name explicitly present in raw input is allowed; version stays null.
        raw = self.root/'history/summary.json'
        source=json.loads(raw.read_text());source['runner']={'name':'k6'}
        raw.write_text(json.dumps(source))
        original['raw_evidence'][0]['sha256']=digest(raw)
        original['runner']['name']='k6'
        path.write_text(json.dumps(original))
        validate(self.root, 'evaluate', run='history', unbound_report_only=True)

    def test_report_execution_reference_must_match_file_and_digest(self):
        original=json.loads(self.result_path.read_text())
        original.update(mode='report-only', verdict='inconclusive', checks={})
        self.result_path.write_text(json.dumps(original))
        validate(self.root, 'evaluate')
        # A task explicitly lacking frozen provenance rejects even an existing reference.
        with self.assertRaisesRegex(AssertionError, 'unbound report identity'):
            validate(self.root, 'evaluate', unbound_report_only=True)
        for change in ('missing', 'digest'):
            with self.subTest(change=change):
                value=copy.deepcopy(original)
                if change=='missing': value['execution']['path']='missing-execution.json'
                else: value['execution']['sha256']='0'*64
                self.result_path.write_text(json.dumps(value))
                with self.assertRaises(AssertionError):validate(self.root, 'evaluate')

    def test_passed_result_rejects_missing_values_and_insufficient_samples(self):
        original=self.result_path.read_text()
        changes={
            'null metric':lambda s:s['metrics'][0].update(value=None),
            'zero samples':lambda s:s['metrics'][0].update(sample_count=0),
            'below minimum':lambda s:s['metrics'][0].update(sample_count=9),
            'fractional samples':lambda s:s['metrics'][0].update(sample_count=60.5),
            'boolean value':lambda s:s['metrics'][0].update(value=True),
            'null actual':lambda s:s['threshold_results'][0].update(actual=None),
            'different metric':lambda s:s['metrics'][0].update(statistic='p99'),
            'different actual':lambda s:s['threshold_results'][0].update(actual=200),
            'different limit':lambda s:s['threshold_results'][0].update(limit=999),
        }
        for name, mutate in changes.items():
            with self.subTest(name=name):
                self.result_path.write_text(original)
                self.mutate_result(lambda r:mutate(r['scenarios'][0]))
                with self.assertRaises(AssertionError):validate(self.root,'evaluate')
        # Zero is a legitimate measured value, unlike null or an empty sample set.
        self.result_path.write_text(original)
        def zero(r):
            r['scenarios'][0]['metrics'][0]['value']=0
            r['scenarios'][0]['threshold_results'][0]['actual']=0
        self.mutate_result(zero)
        validate(self.root,'evaluate')

    def test_deleting_any_required_frozen_check_is_rejected(self):
        original=self.result_path.read_text()
        for key in json.loads(original)['checks']:
            with self.subTest(check=key):
                self.result_path.write_text(original)
                self.mutate_result(lambda r:r['checks'].pop(key))
                with self.assertRaisesRegex(AssertionError,'required frozen check missing'):
                    validate(self.root,'evaluate')

    def test_scope_reference_cannot_be_missing_changed_or_from_other_run(self):
        original=self.result_path.read_text()
        self.mutate_result(lambda r:r['scope'].update(sha256='0'*64))
        with self.assertRaises(AssertionError):validate(self.root,'evaluate')
        self.result_path.write_text(original)
        scope_path=self.root/'test-runs/catalog-load/scope.json'
        scope=json.loads(scope_path.read_text());scope['run_id']='other-run'
        scope_path.write_text(json.dumps(scope));self.rebind_inputs()
        with self.assertRaisesRegex(AssertionError,'scope run/profile mismatch'):
            validate(self.root,'evaluate')

    def test_smoke_and_formal_profiles_cannot_be_mixed(self):
        plan_path=self.root/'perfspec/catalog/plan.json'
        plan=json.loads(plan_path.read_text())
        smoke=copy.deepcopy(plan['profiles'][0]);smoke['id']='smoke'
        smoke['load']['stages'][0].update(duration_seconds=10,target=1)
        smoke['phases'][0]['duration_seconds']=10
        smoke['measurement']['duration_seconds']=10
        plan['profiles'][0]['load']['stages'][0]['target']=20
        plan['profiles'].append(smoke)
        plan_path.write_text(json.dumps(plan))
        self.mutate_result(lambda r:r['load_observation']['stages'][0].update(target=20,actual=20))
        self.rebind_inputs();validate(self.root,'evaluate')
        original=self.result_path.read_text()
        execution_path=self.root/'test-runs/catalog-load/execution.json'
        execution=json.loads(execution_path.read_text())
        for profile_id in ('nonexistent','smoke'):
            with self.subTest(profile=profile_id):
                execution['profile_id']=profile_id
                execution_path.write_text(json.dumps(execution))
                self.result_path.write_text(original)
                self.mutate_result(lambda r:r['execution'].update(sha256=digest(execution_path)))
                with self.assertRaisesRegex(AssertionError,'profile'):
                    validate(self.root,'evaluate')
        # Even relabeling result and scope to smoke cannot reuse formal load data.
        self.mutate_result(lambda r:r.update(profile_id='smoke'))
        scope_path=self.root/'test-runs/catalog-load/scope.json'
        scope=json.loads(scope_path.read_text());scope['profile_id']='smoke'
        scope_path.write_text(json.dumps(scope));self.rebind_inputs()
        with self.assertRaisesRegex(AssertionError,'load stage differs'):
            validate(self.root,'evaluate')

    def test_passed_result_requires_profile_load_and_measurement_window(self):
        original=self.result_path.read_text()
        changes={
            'low load':lambda r:r['load_observation']['stages'][0].update(actual=0),
            'wrong unit':lambda r:r['load_observation'].update(unit='iterations_per_second'),
            'wrong phase':lambda r:r['window'].update(phase='smoke'),
            'short window':lambda r:r['window'].update(finished_at='2026-01-01T00:00:31Z'),
            'outside execution':lambda r:r['window'].update(finished_at='2026-01-01T00:01:02Z'),
            'wrong metric window':lambda r:r['scenarios'][0]['metrics'][0].update(window='smoke'),
        }
        for name, mutate in changes.items():
            with self.subTest(name=name):
                self.result_path.write_text(original);self.mutate_result(mutate)
                with self.assertRaises(AssertionError):validate(self.root,'evaluate')

    def test_multi_profile_result_covers_only_selected_scenarios(self):
        plan_path=self.root/'perfspec/catalog/plan.json'
        plan=json.loads(plan_path.read_text())
        other=copy.deepcopy(plan['scenarios'][0]);other['id']='other'
        plan['scenarios'].append(other)
        other_profile=copy.deepcopy(plan['profiles'][0])
        other_profile.update(id='other-load',scenario_ids=['other'])
        plan['profiles'].append(other_profile)
        plan_path.write_text(json.dumps(plan))
        def add_unobserved(r):
            scenario=copy.deepcopy(r['scenarios'][0])
            scenario.update(id='other',observed=False,metrics=[],evidence=[])
            scenario['threshold_results'][0].update(actual=None,status='unknown')
            r['scenarios'].append(scenario)
        self.mutate_result(add_unobserved);self.rebind_inputs()
        validate(self.root,'evaluate')
        self.mutate_result(lambda r:r['scenarios'][1].update(observed=True))
        with self.assertRaisesRegex(AssertionError,'outside selected profile'):
            validate(self.root,'evaluate')

    def test_script_drift_rejects_current_pass_preserves_historical_result(self):
        original=self.result_path.read_bytes()
        script=self.root/'perfspec/catalog/assets/k6/catalog.js'
        script.write_text(script.read_text()+'\n// changed after execution\n')
        with self.assertRaisesRegex(AssertionError,'changed source'):
            validate(self.root,'evaluate')
        self.assertEqual(self.result_path.read_bytes(),original)
        # Historical observation can remain recorded with an explicit stale verdict.
        self.mutate_result(lambda r:r.update(verdict='stale'))
        validate(self.root,'evaluate')

    def test_dataset_drift_rejects_current_pass(self):
        dataset=self.root/'perfspec/catalog/data/catalog.csv'
        dataset.parent.mkdir();dataset.write_text('id\nsynthetic-1\n')
        plan_path=self.root/'perfspec/catalog/plan.json'
        plan=json.loads(plan_path.read_text())
        plan['data']['dataset_paths']=['perfspec/catalog/data/catalog.csv']
        plan_path.write_text(json.dumps(plan))
        scope_path=self.root/'test-runs/catalog-load/scope.json'
        scope=json.loads(scope_path.read_text())
        scope['sources'].append({'id':'data','kind':'dataset','path':'perfspec/catalog/data/catalog.csv','sha256':digest(dataset)})
        scope_path.write_text(json.dumps(scope));self.rebind_inputs()
        validate(self.root,'evaluate')
        dataset.write_text('id\nsynthetic-2\n')
        with self.assertRaisesRegex(AssertionError,'changed source'):
            validate(self.root,'evaluate')

    def test_execution_input_hashes_must_match_frozen_sources(self):
        execution_path=self.root/'test-runs/catalog-load/execution.json'
        execution=json.loads(execution_path.read_text())
        original=self.result_path.read_text()
        script='perfspec/catalog/assets/k6/catalog.js'
        for mutation in ('missing','different'):
            with self.subTest(mutation=mutation):
                changed=copy.deepcopy(execution)
                for key in ('input_hashes_before','input_hashes_after'):
                    if mutation=='missing':changed[key].pop(script)
                    else:changed[key][script]='0'*64
                execution_path.write_text(json.dumps(changed))
                self.result_path.write_text(original)
                self.mutate_result(lambda r:r['execution'].update(sha256=digest(execution_path)))
                with self.assertRaisesRegex(AssertionError,'inputs differ from frozen'):
                    validate(self.root,'evaluate')

    def test_required_runner_input_cannot_be_removed_from_scope(self):
        scope_path=self.root/'test-runs/catalog-load/scope.json'
        scope=json.loads(scope_path.read_text())
        scope['sources']=[s for s in scope['sources'] if s['id']!='script']
        scope_path.write_text(json.dumps(scope));self.rebind_inputs()
        with self.assertRaisesRegex(AssertionError,'required input missing'):
            validate(self.root,'evaluate')

    def test_threshold_fields_validated_before_evaluation(self):
        plan_path=self.root/'perfspec/catalog/plan.json'
        original=json.loads(plan_path.read_text())
        for status in ('ready','draft'):
            for field in original['scenarios'][0]['thresholds'][0]:
                with self.subTest(status=status,missing=field):
                    plan=copy.deepcopy(original);plan['status']=status
                    plan['scenarios'][0]['thresholds'][0].pop(field)
                    plan_path.write_text(json.dumps(plan))
                    with self.assertRaisesRegex(AssertionError,'missing fields'):
                        validate(self.root,'plan')
        draft=copy.deepcopy(original);draft.update(status='draft',blockers=['SLA unit and value unconfirmed'])
        draft['scenarios'][0]['thresholds'][0].update(unit=None,value=None)
        plan_path.write_text(json.dumps(draft));validate(self.root,'plan')
        draft.update(status='ready',blockers=[])
        plan_path.write_text(json.dumps(draft))
        with self.assertRaisesRegex(AssertionError,'threshold unit'):
            validate(self.root,'plan')

    def test_execution_reference_rejects_inline_details(self):
        self.mutate_result(lambda r:r.update(execution={'status':'completed','exit_code':0}))
        with self.assertRaisesRegex(AssertionError,'missing fields'):
            validate(self.root,'evaluate')

    def test_synthetic_freeze_record_evaluate_and_failure_recovery(self):
        engine=module(ROOT/'skills/_test-run-shared/scripts/test_run.py')
        p=json.loads((self.root/'perfspec/catalog/plan.json').read_text())
        result=json.loads(self.result_path.read_text())
        now=lambda:datetime.now(timezone.utc).isoformat()
        scope={'run_id':'synthetic-check','mode':'local',
            'sources':[{'id':'plan','kind':'local-check','path':'perfspec/catalog/plan.json'},
                       {'id':'script','kind':'runner-definition','path':'perfspec/catalog/assets/k6/catalog.js'}],
            'targets':[p['target']],
            'capabilities':[{'id':'fixture','target_id':'api','availability':'available','authorization':'granted','actions':['read'],'scope':'synthetic files only; no HTTP request or native runner','basis':'unit test fixture','checked_at':now()}],
            'checks':[{'id':key,'case_id':'synthetic-catalog','source_id':'plan','requirement_refs':[], 'oracle':check['basis'],'target_id':'api','required':True,'effect':'read','cleanup':'not-required','depends_on':[],'capability_ids':['fixture'],'binding':{'runner':'observation','selector':'/checks/'+key}} for key,check in result['checks'].items()]}
        draft=self.root/'scope-draft.json';draft.write_text(json.dumps(scope))
        # Each variant starts from a legal baseline; only the SLA observation changes.
        for label,status in [('baseline','passed'),('sla-failure','failed'),('recovery','passed')]:
            run=self.root/'test-runs'/label
            engine.freeze(draft,self.root,run)
            obs=copy.deepcopy(result)
            obs['checks']['PERF_SLA']['status']=status
            obs['checks']['PERF_SLA']['actual']='synthetic P95 900 > 500' if status=='failed' else 'synthetic P95 100 <= 500'
            evidence=run/'observation.json';evidence.write_text(json.dumps(obs))
            for key,check in obs['checks'].items():
                instant=now()
                attempt={'id':key,'check_id':key,'target':p['target'],'started_at':instant,'finished_at':instant,'status':check['status'],'cleanup_status':'not-required','evidence':[{'path':str(evidence.relative_to(self.root)),'collector':'synthetic-test','collected_at':instant},{'path':'test-runs/catalog-load/raw/observation.json','collector':'synthetic-fixture','collected_at':instant}]}
                path=self.root/'attempt.json';path.write_text(json.dumps(attempt))
                engine.record(path,self.root,run)
            targets=self.root/'targets.json';targets.write_text(json.dumps([p['target']]))
            assessed=engine.evaluate(self.root,run,[p["target"]])
            self.assertEqual(assessed['acceptance_status'],status)
            self.assertTrue((run/'scope.json').is_file())

if __name__=='__main__':unittest.main()
