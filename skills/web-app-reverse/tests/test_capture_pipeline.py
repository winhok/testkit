import base64
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from capture_io import export_capture, verified_sources
from build_test_map import build
from export_local import export_local

ORIGIN = 'https://example.invalid'


def entry(path, text=None, mime='application/javascript', method='GET', status=200, encoding=None):
    content = {'mimeType': mime}
    if text is not None:
        content['text'] = text
    if encoding is not None:
        content['encoding'] = encoding
    return {'request': {'url': ORIGIN + path, 'method': method, 'headers': [{'name':'Authorization','value':'SECRET'}]},
            'response': {'status':status, 'content':content}}


def fixture():
    return {'log': {'version':'1.2','entries':[
        entry('/assets/main.js?token=SECRET', '''
import './detail.js';
const routes=[{path:'/reports',children:[{path:':id'}]}];
createBrowserRouter(routes);
fetch('/api/reports', {method:'POST'});
localStorage.setItem('filter', 'SECRET');
//# sourceMappingURL=main.js.map
'''),
        entry('/assets/detail.js', 'export const detail = true;'),
        entry('/assets/main.js.map', json.dumps({'version':3,'file':'main.js','sources':['source.js'],'sourcesContent':['const x=1']}), 'application/json'),
        entry('/api/reports?token=SECRET', '{"private":"SECRET"}', 'application/json','POST',403),
        entry('/reports', '<form><input required value="SECRET"><button>Save</button></form>', 'text/html'),
    ]}}


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.capture = self.root/'session.har'
        self.capture.write_text(json.dumps(fixture()))
        self.export = self.root/'export'

    def run_export(self):
        return export_capture(self.capture,self.export,ORIGIN)

    def test_full_offline_pipeline_and_privacy(self):
        manifest = self.run_export()
        result = build(self.export,ORIGIN)
        self.assertEqual(manifest['coverage']['exported_sources'],4)
        self.assertEqual({row['path'] for row in result['maps']['pages']}, {'/reports','/reports/:id'})
        endpoint = next(row for row in result['maps']['communications'] if row['kind']=='endpoint')
        self.assertEqual(endpoint['method'],'POST')
        self.assertEqual(endpoint['reconciliation'],'historical-match')
        self.assertEqual(result['coverage']['application'],'unknown')
        self.assertNotIn('SECRET',json.dumps(result))
        self.assertTrue(any(row['relation']=='dynamic-import' or row['relation']=='static-import' for row in result['maps']['behaviors']))
        self.assertTrue(any(row['relation']=='declares-source-map' for row in result['maps']['behaviors']))
        self.assertTrue(any(row['kind']=='required-input' for row in result['maps']['test_candidates']))
        self.assertTrue(all(row['provenance']['sha256'] and row['actions'] and row['oracle'] and row['test_data'] for row in result['maps']['test_candidates']))
        self.assertTrue(any(row['reason']=='recorded-request-failure' for row in result['unknowns']))
        self.assertTrue(any(row['reason']=='shared-module-is-not-action-causality' for row in result['unknowns']))

    def test_export_no_overwrite_or_escape(self):
        manifest = self.run_export()
        with self.assertRaises(FileExistsError):
            self.run_export()
        self.assertEqual(json.loads((self.export/'manifest.json').read_text()),manifest)
        manifest['resources'][0]['file']='../outside.js'
        (self.export/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError,'invalid source path'):
            verified_sources(self.export)

    def test_source_tamper_is_rejected(self):
        manifest = self.run_export()
        (self.export/manifest['resources'][0]['file']).write_text('changed')
        with self.assertRaisesRegex(ValueError,'integrity'):
            build(self.export,ORIGIN)

    def test_url_and_origin_mismatch_rejected(self):
        self.run_export()
        with self.assertRaisesRegex(ValueError,'site origin'):
            build(self.export,'https://other.example.invalid')
        manifest=json.loads((self.export/'manifest.json').read_text())
        manifest['resources'][0]['source_url']=ORIGIN+'/changed.js'
        (self.export/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError,'URL integrity'):
            verified_sources(self.export)

    def test_origin_method_and_missing_body_remain_separate(self):
        data=fixture()
        data['log']['entries'] += [entry('/assets/missing.js'), entry('/api/reports', '{}','application/json','GET')]
        foreign=entry('/assets/foreign.js','fetch("/api/reports")')
        foreign['request']['url']='https://other.example.invalid/assets/foreign.js'
        data['log']['entries'].append(foreign)
        self.capture.write_text(json.dumps(data))
        manifest=self.run_export()
        self.assertEqual(manifest['coverage']['unavailable_sources'],1)
        self.assertTrue(any(row['reason']=='outside-selected-origins' for row in manifest['unknowns']))
        result=build(self.export,ORIGIN)
        endpoint=next(row for row in result['maps']['communications'] if row['kind']=='endpoint')
        self.assertEqual(endpoint['historical_matches'],['network-3'])

    def test_duplicate_url_variants_are_ambiguous(self):
        data=fixture()
        data['log']['entries'].append(entry('/assets/detail.js','export const old=true'))
        self.capture.write_text(json.dumps(data))
        self.run_export()
        result=build(self.export,ORIGIN)
        self.assertTrue(any(row['reason']=='ambiguous-resource' for row in result['unknowns']))
        self.assertEqual(len([row for row in result['maps']['resources'] if row['path']=='/assets/detail.js']),2)

    def test_base64_invalid_and_partial_capture(self):
        data=fixture()
        body=data['log']['entries'][1]['response']['content']
        body.update(text=base64.b64encode(b'export const ok = true;').decode(),encoding='base64')
        self.capture.write_text(json.dumps(data))
        self.run_export()
        self.assertEqual(len(verified_sources(self.export)[1]),4)
        body['text']='not base64!'
        self.capture.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'base64'):
            export_capture(self.capture,self.root/'bad',ORIGIN)
        self.assertFalse((self.root/'bad').exists())

    def test_relative_fetch_needs_document_base(self):
        data=fixture()
        data['log']['entries'][1]['response']['content']['text']='fetch("api/items")'
        self.capture.write_text(json.dumps(data))
        self.run_export()
        without=build(self.export,ORIGIN)
        self.assertTrue(any(row['reason']=='request-document-base-required' for row in without['unknowns']))
        with_base=build(self.export,ORIGIN,ORIGIN+'/app/')
        self.assertTrue(any(row.get('path')=='/app/api/items' for row in with_base['maps']['communications']))

    def test_capture_projection_and_resource_limits(self):
        data={'schema_version':1,'kind':'web-page-capture','coverage':{'truncated':True,'secret':'SECRET'},'resources':[
            {'url':ORIGIN+'/main.js','mimeType':'text/javascript','reason':'SECRET'}]}
        self.capture.write_text(json.dumps(data))
        manifest=self.run_export()
        self.assertTrue(manifest['coverage']['producer']['truncated'])
        self.assertEqual(manifest['resources'][0]['reason'],'body-not-retained')
        result=build(self.export,ORIGIN)
        self.assertNotIn('SECRET',json.dumps(result))
        data['resources'] *= 501
        self.capture.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'record limit'):
            export_capture(self.capture,self.root/'too-many',ORIGIN)

    def test_redacted_paths_do_not_merge_different_requests(self):
        data=fixture()
        data['log']['entries'][0]['response']['content']['text']='fetch("/api/orders/123456");fetch("/api/orders/654321")'
        data['log']['entries'].append(entry('/api/orders/654321','{}','application/json'))
        self.capture.write_text(json.dumps(data))
        self.run_export()
        result=build(self.export,ORIGIN)
        endpoints=[row for row in result['maps']['communications'] if row['kind']=='endpoint']
        self.assertEqual(len(endpoints),2)
        self.assertEqual(len({row['path'] for row in endpoints}),1)
        self.assertEqual(len({row['id'] for row in endpoints}),2)
        self.assertEqual([row['reconciliation'] for row in endpoints],['not-observed-in-capture','historical-match'])

    def test_local_exports_use_ast_and_preserve_module_layout(self):
        local=self.root/'static'
        (local/'chunks').mkdir(parents=True)
        (local/'main.js').write_text('import("./chunks/detail.js");createBrowserRouter([{path:"/local"}]);')
        (local/'chunks'/'detail.js').write_text('fetch("/api/local")')
        report=export_local(local,self.export,ORIGIN,'/assets/')
        self.assertEqual(report['coverage']['producer']['kind'],'local-directory')
        result=build(self.export,ORIGIN)
        self.assertEqual(result['maps']['pages'][0]['path'],'/local')
        self.assertTrue(any(edge['relation']=='dynamic-import' and edge['resolution']=='resolved' for edge in result['maps']['behaviors']))
        with self.assertRaises(ValueError):
            export_local(local,self.root/'invalid-base',ORIGIN,'//other/')

    def test_local_symlink_escape_is_skipped(self):
        local=self.root/'static'
        local.mkdir()
        (local/'main.js').write_text('navigate("/local")')
        outside=self.root/'outside.js'
        outside.write_text('navigate("/outside")')
        try:
            (local/'linked.js').symlink_to(outside)
        except OSError:
            if sys.platform == 'win32':
                self.skipTest('Windows symlink permission unavailable')
            raise
        manifest=export_local(local,self.export,ORIGIN)
        self.assertEqual(len(manifest['resources']),1)

    def test_malformed_json_and_failed_response_keep_no_source(self):
        self.capture.write_text('{"log":{},"log":{}}')
        with self.assertRaisesRegex(ValueError,'duplicate'):
            self.run_export()
        data=fixture()
        data['log']['entries'][0]['response']['status']=403
        self.capture.write_text(json.dumps(data))
        manifest=self.run_export()
        self.assertEqual(manifest['resources'][0]['reason'],'non-success-response')
        result=build(self.export,ORIGIN)
        self.assertEqual(result['maps']['pages'],[])

    def test_private_files_and_output_are_exclusive(self):
        self.run_export()
        if sys.platform != 'win32':
            self.assertEqual((self.export.stat().st_mode & 0o777),0o700)
            self.assertEqual(((self.export/'manifest.json').stat().st_mode & 0o777),0o600)
        from capture_io import private_json
        output=self.root/'report.json'
        private_json(output,{'value':'first'})
        with self.assertRaises(FileExistsError):
            private_json(output,{'value':'second'})
        self.assertEqual(json.loads(output.read_text()),{'value':'first'})

    def test_cli_uses_real_pipeline_and_safe_errors(self):
        run=subprocess.run([sys.executable,str(SCRIPTS/'export_capture.py'),'--input',str(self.capture),
                            '--output-dir',str(self.export),'--site-origin',ORIGIN],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stdout)
        output=self.root/'inspection-map.json'
        run=subprocess.run([sys.executable,str(SCRIPTS/'build_test_map.py'),'--export-dir',str(self.export),
                            '--site-origin',ORIGIN,'--output',str(output)],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stdout)
        self.assertTrue(output.is_file())
        self.assertNotIn('SECRET',run.stdout+run.stderr)


if __name__=='__main__':
    unittest.main()
