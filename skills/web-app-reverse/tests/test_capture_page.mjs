import assert from 'node:assert/strict';
import {captureScriptSources} from '../scripts/capture_page.mjs';

const origin='https://example.invalid';
let commands=[];
const page={
  url:async()=> origin+'/reports?token=PRIVATE',
  events:async()=> [
    {method:'Debugger.scriptParsed',params:{url:origin+'/main.js',scriptId:'1'}},
    {method:'Debugger.scriptParsed',params:{url:'https://other.example.invalid/foreign.js',scriptId:'2'}},
    {method:'Network.responseReceived',params:{headers:{Authorization:'PRIVATE'}}},
  ],
  cdp:async(method,args)=>{
    commands.push([method,args]);
    if(method==='Debugger.getScriptSource') return {scriptSource:'const routes=[];'};
    return {};
  },
};
const capture=await captureScriptSources(page,[origin]);
assert.equal(capture.resources.length,1);
assert.equal(capture.resources[0].collection,'debugger-source');
assert.deepEqual(commands.map(row=>row[0]),['Debugger.enable','Debugger.getScriptSource','Debugger.disable']);
assert.ok(!JSON.stringify(capture).includes('PRIVATE'));
commands=[];
await assert.rejects(captureScriptSources(page,['https://other.example.invalid']),/target-unconfirmed/);
assert.equal(commands.length,0);
page.cdp=async method=> {commands.push([method]);if(method==='Debugger.getScriptSource')throw new Error('gone');return {};};
const missing=await captureScriptSources(page,[origin]);
assert.deepEqual(missing.coverage.gaps,['script-source-unavailable']);
assert.equal(commands.at(-1)[0],'Debugger.disable');
page.cdp=async method=> {commands.push([method]);if(method==='Debugger.getScriptSource')return {scriptSource:'x'.repeat(2*1024*1024+1)};return {};};
assert.deepEqual((await captureScriptSources(page,[origin])).coverage.gaps,['script-size-limit']);
let calls=0;
page.url=async()=> ++calls === 1 ? origin+'/' : 'https://other.example.invalid/';
await assert.rejects(captureScriptSources(page,[origin]),/target-changed/);
assert.equal(commands.at(-1)[0],'Debugger.disable');
console.log('Browser retained-source capture scope, limits, gaps and cleanup passed');
