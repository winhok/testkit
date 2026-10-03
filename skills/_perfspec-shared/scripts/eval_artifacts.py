"""Artifact assertions for isolated PerfSpec evals; no execution or SLA calculation.

The grader supplies TESTKIT_ROOT. This validates delivered files and bindings,
not external facts, native tool compatibility, or model performance.
"""
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate(root, stage, spec='perfspec/catalog', run='test-runs/catalog-load', *, unbound_report_only=False):
    root = Path(root).resolve()

    def file(name):
        p = (root / name).resolve()
        assert p.is_relative_to(root) and p.is_file(), f'missing or unsafe artifact: {name}'
        return p

    def load(name):
        value = json.loads(file(name).read_text(), parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)))
        assert isinstance(value, dict), f'object required: {name}'
        return value

    def fields(value, required):
        assert set(required) <= value.keys(), f'missing fields: {set(required) - value.keys()}'

    def refs(items):
        assert isinstance(items, list)
        for item in items:
            assert digest(file(item['path'])) == item['sha256'], f"changed source: {item['path']}"

    def markdown(name):
        assert len(file(name).read_text().strip()) >= 30, f'empty report: {name}'

    def number(value, *, positive=False):
        return (type(value) in (int, float) and math.isfinite(value)
                and (value > 0 if positive else value >= 0))

    def finite(value):
        return type(value) in (int, float) and math.isfinite(value)

    def timestamp(value):
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        assert parsed.tzinfo is not None, 'window timezone required'
        return parsed

    def thresholds(p):
        for scenario in p['scenarios']:
            assert isinstance(scenario['thresholds'], list), 'thresholds must be a list'
            ids = []
            for threshold in scenario['thresholds']:
                fields(threshold, ['id', 'metric', 'selector', 'statistic', 'operator', 'value', 'unit', 'basis'])
                assert isinstance(threshold['id'], str) and threshold['id'].strip(), 'threshold ID required'
                ids.append(threshold['id'])
                for key in ('metric', 'selector', 'statistic', 'unit', 'basis'):
                    value = threshold[key]
                    assert (p['status'] == 'draft' and value is None) or (isinstance(value, str) and value.strip()), f'invalid threshold {key}'
                assert threshold['operator'] in ('<', '<=', '>', '>=', '==', '!=') or (p['status'] == 'draft' and threshold['operator'] is None), 'invalid threshold operator'
                assert finite(threshold['value']) or (p['status'] == 'draft' and threshold['value'] is None), 'invalid threshold value'
            assert len(ids) == len(set(ids)), 'duplicate plan threshold ID'

    def ready_profiles(p):
        assert isinstance(p['profiles'], list) and p['profiles'], 'ready plan needs profiles'
        required = {s['id'] for s in p['scenarios'] if s['required']}
        covered = set()
        profile_ids = [profile['id'] for profile in p['profiles']]
        assert len(profile_ids) == len(set(profile_ids)), 'duplicate profile ID'
        for profile in p['profiles']:
            scenario_ids = profile['scenario_ids']
            assert scenario_ids and len(scenario_ids) == len(set(scenario_ids)), 'empty or duplicate profile scenarios'
            covered.update(scenario_ids)
            stages = profile['load']['stages']
            assert stages and all(number(s['duration_seconds'], positive=True) and number(s['target']) for s in stages), 'invalid load stages'
            assert any(s['target'] > 0 for s in stages), 'no positive load'
            phases = profile['phases']
            assert phases and all(number(phase['duration_seconds'], positive=True) for phase in phases), 'invalid phases'
            phase_ids = [phase['name'] for phase in phases]
            assert len(phase_ids) == len(set(phase_ids)), 'duplicate phase name'
            duration = sum(s['duration_seconds'] for s in stages)
            assert sum(phase['duration_seconds'] for phase in phases) <= duration, 'phases exceed load duration'
            measurement = profile['measurement']
            assert measurement['phase'] in phase_ids, 'missing measurement phase'
            phase_duration = next(phase['duration_seconds'] for phase in phases if phase['name'] == measurement['phase'])
            assert number(measurement['duration_seconds'], positive=True) and measurement['duration_seconds'] <= phase_duration, 'invalid measurement window'
            phase_start = 0
            for phase in phases:
                if phase['name'] == measurement['phase']:
                    break
                phase_start += phase['duration_seconds']
            phase_end = phase_start + phase_duration
            stage_start = 0
            measured_load = False
            for stage in stages:
                stage_end = stage_start + stage['duration_seconds']
                if stage['target'] > 0 and max(stage_start, phase_start) < min(stage_end, phase_end):
                    measured_load = True
                stage_start = stage_end
            assert measured_load, 'measurement phase has no positive load'
        assert required <= covered, 'required scenario missing from profiles'

    def execution_binding(result):
        exec_ref = result['execution']
        assert isinstance(exec_ref, dict), 'execution reference required'
        fields(exec_ref, ['path', 'sha256'])
        assert exec_ref['sha256'] == digest(file(exec_ref['path'])), 'execution digest mismatch'
        e = load(exec_ref['path'])
        assert result['run_id'] == e['run_id'] and result['runner'] == e['runner']
        assert result['target'] == e['target'] and result['spec_id'] == e['spec_id']
        if result['plan_sha256'] is not None:
            assert result['plan_sha256'] == digest(file(spec + '/plan.json')), 'plan digest mismatch'
            assert e['input_hashes_before'][spec + '/plan.json'] == result['plan_sha256'], 'execution plan binding mismatch'
        return e

    if stage == 'analysis':
        q = load(spec + '/requirements.json')
        fields(q, ['schema_version', 'spec_id', 'status', 'sources', 'scope', 'out_of_scope', 'goals', 'scenarios', 'decisions', 'blockers'])
        assert q['schema_version'] == 1 and q['status'] in ('draft', 'ready')
        refs(q['sources'])
        markdown(spec + '/analysis.md')
        return q
    if stage in ('plan', 'generate'):
        p = load(spec + '/plan.json')
        fields(p, ['schema_version', 'spec_id', 'status', 'sources', 'target', 'runner', 'scenarios', 'profiles', 'data', 'monitoring', 'stop_conditions', 'comparison', 'blockers'])
        assert p['schema_version'] == 1 and p['status'] in ('draft', 'ready')
        assert isinstance(p['blockers'], list)
        if p['status'] == 'ready':
            assert not p['blockers']
        refs(p['sources'])
        ids = [s['id'] for s in p['scenarios']]
        assert ids and len(ids) == len(set(ids))
        assert all(type(s['required']) is bool for s in p['scenarios'])
        thresholds(p)
        for profile in p['profiles']:
            assert set(profile['scenario_ids']) <= set(ids)
            model = profile['load']['model']
            assert profile['load']['unit'] == {'open': 'iterations_per_second', 'closed': 'users'}[model]
        if p['status'] == 'ready':
            ready_profiles(p)
        markdown(spec + '/plan.md')
        if stage == 'plan':
            return p
        assert p['status'] == 'ready'
        m = load(spec + '/asset-manifest.json')
        fields(m, ['schema_version', 'spec_id', 'plan_sha256', 'runner', 'expected_version', 'sources', 'files', 'mappings', 'datasets', 'dependencies', 'unsupported_features', 'warnings', 'validation'])
        assert m['schema_version'] == 1 and m['spec_id'] == p['spec_id']
        assert m['plan_sha256'] == digest(file(spec + '/plan.json'))
        assert m['runner'] == p['runner']['name'] and m['files']
        refs(m['sources']); refs(m['files'])
        assert p['runner']['asset_path'] in [f['path'] for f in m['files']]
        required = {(s['id'], step['id']) for s in p['scenarios'] if s['required'] for step in s['steps']}
        actual = {(item['scenario_id'], item['step_id']) for item in m['mappings']}
        assert required <= actual, 'required step mapping missing'
        return m
    assert stage == 'evaluate', f'unsupported assertion stage: {stage}'
    result = load(run + '/performance-result.json')
    fields(result, ['schema_version', 'spec_id', 'run_id', 'plan_sha256', 'runner', 'target', 'mode', 'execution', 'raw_evidence', 'window', 'scenarios', 'checks', 'execution_validity', 'load_status', 'functional_status', 'sla_status', 'cleanup_status', 'verdict', 'reasons', 'limitations', 'comparison', 'diagnosis'])
    assert result['schema_version'] == 1
    assert result['verdict'] in ('passed', 'failed', 'blocked', 'inconclusive', 'stale')
    assert isinstance(result['checks'], dict)
    for key, check in result['checks'].items():
        fields(check, ['id', 'status', 'actual', 'basis', 'method'])
        assert key == check['id']
        assert check['status'] in ('passed', 'failed', 'blocked', 'skipped', 'inconclusive', 'error')
        assert check['method'] in ('human', 'tool')
        assert isinstance(check['actual'], str) and check['actual'].strip()
        assert isinstance(check['basis'], str) and check['basis'].strip()
    refs(result['raw_evidence'])
    assert result['raw_evidence'], 'raw support missing'
    if result['mode'] == 'report-only':
        assert result['verdict'] != 'passed' and not result['checks']
        assert result['limitations']
        if unbound_report_only:
            assert all(result[key] is None for key in ('spec_id', 'run_id', 'plan_sha256', 'target', 'execution')), 'unbound report identity must be null'
        if result['execution'] is not None:
            execution_binding(result)
        else:
            # Identity must occur explicitly in supplied raw JSON, never be inferred
            # from metrics, limitations, or a newly invented execution reference.
            sources = []
            for ref in result['raw_evidence']:
                if file(ref['path']).suffix == '.json':
                    sources.append(load(ref['path']))
            for key in ('spec_id', 'run_id', 'target', 'window'):
                if result[key] is not None:
                    assert any(source.get(key) == result[key] for source in sources), f'unsupported report identity: {key}'
            assert result['plan_sha256'] is None, 'unbound plan digest must be null'
            assert isinstance(result['runner'], dict)
            for key in ('name', 'version'):
                value = result['runner'][key]
                if value is not None:
                    assert any(isinstance(source.get('runner'), dict) and source['runner'].get(key) == value for source in sources), f'unsupported runner {key}'
            assert all(s['required'] is None for s in result['scenarios']), 'unbound scenario required must be null'
    else:
        assert result['mode'] in ('local', 'acceptance')
        p = load(spec + '/plan.json')
        thresholds(p)
        assert result['plan_sha256'] == digest(file(spec + '/plan.json'))
        assert result['target'] == p['target'] and result['spec_id'] == p['spec_id']
        e = execution_binding(result)
        fields(result, ['profile_id', 'scope', 'load_observation'])
        profiles = {profile['id']: profile for profile in p['profiles']}
        assert e['profile_id'] in profiles, 'execution profile missing from plan'
        assert result['profile_id'] == e['profile_id'], 'result profile differs from execution'
        profile = profiles[e['profile_id']]
        selected = set(profile['scenario_ids'])
        scope_ref = result['scope']
        refs([scope_ref])
        scope = load(scope_ref['path'])
        assert scope['kind'] == 'test-scope' and timestamp(scope['frozen_at']) <= timestamp(e['started_at']), 'scope was not frozen before execution'
        assert e['scope_sha256'] == scope_ref['sha256'], 'execution scope digest mismatch'
        assert scope['run_id'] == result['run_id'] and scope['profile_id'] == result['profile_id'], 'frozen scope run/profile mismatch'
        assert any(s['path'] == spec + '/plan.json' and s['sha256'] == result['plan_sha256'] for s in scope['sources']), 'scope plan binding missing'
        frozen_checks = {check['id']: check for check in scope['checks']}
        assert len(frozen_checks) == len(scope['checks']), 'duplicate frozen check ID'
        assert all(type(check['required']) is bool for check in frozen_checks.values())
        required_checks = {key for key, check in frozen_checks.items() if check['required']}
        assert required_checks and required_checks <= result['checks'].keys(), 'required frozen check missing'
        assert result['checks'].keys() <= frozen_checks.keys(), 'unfrozen result check'
        expected = {s['id'] for s in p['scenarios']}
        assert selected and selected <= expected, 'profile scenario range invalid'
        actual = [s['id'] for s in result['scenarios']]
        assert len(actual) == len(set(actual)) and set(actual) == expected
        planned = {s['id']: s for s in p['scenarios']}
        for scenario in result['scenarios']:
            source = planned[scenario['id']]
            assert type(scenario['required']) is bool and scenario['required'] == source['required'], 'scenario required differs from plan'
            threshold_ids = [t['id'] for t in scenario['threshold_results']]
            expected_ids = [t['id'] for t in source['thresholds']]
            assert len(expected_ids) == len(set(expected_ids)), 'duplicate plan threshold ID'
            assert len(threshold_ids) == len(set(threshold_ids)) and set(threshold_ids) == set(expected_ids), 'threshold coverage differs from plan'
        if result['verdict'] == 'passed':
            assert p['status'] == 'ready', 'passed result requires ready plan'
            ready_profiles(p)
            assert all(not s['observed'] or s['id'] in selected for s in result['scenarios']), 'observed scenario outside selected profile'
            assert result['execution_validity'] == 'valid' and result['load_status'] == 'met'
            assert result['functional_status'] == result['sla_status'] == 'passed'
            assert result['cleanup_status'] in ('passed', 'not-required')
            assert e['inputs_unchanged'] and e['input_hashes_before'] == e['input_hashes_after']
            frozen_inputs = {source['path']: source['sha256'] for source in scope['sources']}
            assert len(frozen_inputs) == len(scope['sources']), 'duplicate frozen input path'
            required_paths = {spec + '/plan.json', p['runner']['asset_path'], *p['data']['dataset_paths']}
            assert required_paths <= frozen_inputs.keys(), 'required input missing from frozen scope'
            assert e['input_hashes_before'] == frozen_inputs and e['input_hashes_after'] == frozen_inputs, 'execution inputs differ from frozen sources'
            refs(scope['sources'])
            refs(p['sources'])
            assert result['checks'] and all(c['status'] == 'passed' for c in result['checks'].values())
            load_observation = result['load_observation']
            assert load_observation['model'] == profile['load']['model'] and load_observation['unit'] == profile['load']['unit'], 'load model/unit differs from profile'
            stages = load_observation['stages']
            assert len(stages) == len(profile['load']['stages']), 'load stage coverage mismatch'
            tolerance = profile['measurement']['load_tolerance_pct']
            assert number(tolerance) and tolerance < 100, 'invalid load tolerance'
            for observed, planned_stage in zip(stages, profile['load']['stages']):
                assert observed['duration_seconds'] == planned_stage['duration_seconds'] and observed['target'] == planned_stage['target'], 'load stage differs from profile'
                assert number(observed['actual']), 'missing actual load'
                assert abs(observed['actual'] - planned_stage['target']) <= planned_stage['target'] * tolerance / 100, 'observed load outside tolerance'
            window = result['window']
            assert window['phase'] == profile['measurement']['phase'], 'measurement phase differs from profile'
            phase_windows = [w for w in e['phase_windows'] if w['name'] == window['phase']]
            assert len(phase_windows) == 1, 'execution measurement phase missing or duplicate'
            start, end = timestamp(window['started_at']), timestamp(window['finished_at'])
            phase = phase_windows[0]
            assert timestamp(e['started_at']) <= timestamp(phase['started_at']) <= start < end <= timestamp(phase['finished_at']) <= timestamp(e['finished_at']), 'measurement window outside execution phase'
            assert (end - start).total_seconds() >= profile['measurement']['duration_seconds'], 'measurement window too short'
            for scenario in result['scenarios']:
                if planned[scenario['id']]['required'] and scenario['id'] in selected:
                    assert scenario['observed'] is True and scenario['metrics'], 'required scenario unobserved or missing metrics'
                    assert all(t['status'] == 'passed' for t in scenario['threshold_results'])
                    source = planned[scenario['id']]
                    minimum = max(source['sample_policy']['min_samples'], profile['measurement']['min_samples'], 1)
                    for metric in scenario['metrics']:
                        assert finite(metric['value']), 'missing/nonfinite metric value'
                        assert type(metric['sample_count']) is int and metric['sample_count'] >= minimum, 'missing/insufficient samples'
                        assert metric['window'] == window['phase'], 'metric window differs from profile'
                    thresholds = {t['id']: t for t in source['thresholds']}
                    for measured in scenario['threshold_results']:
                        threshold = thresholds[measured['id']]
                        assert finite(measured['actual']), 'missing/nonfinite threshold actual'
                        assert measured['limit'] == threshold['value'] and measured['operator'] == threshold['operator'], 'threshold definition differs from plan'
                        matches = [m for m in scenario['metrics'] if all(m[key] == threshold[key] for key in ('selector', 'metric', 'statistic', 'unit'))]
                        assert len(matches) == 1 and matches[0]['value'] == measured['actual'], 'threshold metric missing or inconsistent'
    markdown(run + '/performance-report.md')
    return result
