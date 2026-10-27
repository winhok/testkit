import assert from 'node:assert/strict';
import {capturePage,captureScriptSources} from '../scripts/capture_page.mjs';

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

// Same-origin navigation must not combine old structure with a new page's scripts.
let reads=0;
page.url=async()=> origin + (++reads===1 ? '/login' : '/reports');
await assert.rejects(captureScriptSources(page,[origin]),/target-changed/);
assert.equal(commands.at(-1)[0],'Debugger.disable');

let pageUrl=origin+'/login';
const movingPage={url:async()=>pageUrl,evaluate:async()=>{
  pageUrl=origin+'/reports';
  return {resources:[],coverage:{}};
},cdp:async()=>{throw new Error('must not attach to a changed target')}};
await assert.rejects(capturePage(movingPage,[origin]),/target-changed/);
console.log('Same-origin navigation guards passed');

// Exercise the real browser callback against a small DOM seam with large inline scripts.
const inlinePage={url:async()=>origin+'/',evaluate:async(fn,arg)=>{
  globalThis.location={origin,href:origin+'/'};
  globalThis.document={baseURI:origin+'/',scripts:Array.from({length:5},()=>({src:'',type:'',textContent:'x'.repeat(2*1024*1024)})),
    querySelectorAll:()=>[],createElement:()=>({append(){},outerHTML:'<main></main>'})};
  return fn(arg);
}};
const bounded=await capturePage(inlinePage,[origin],{includeScriptSources:false});
assert.equal(bounded.coverage.truncated,true);
assert.equal(bounded.resources.filter(row=>row.reason==='body-budget').length,1);
assert.equal(bounded.resources.filter(row=>row.text?.length===2*1024*1024).length,4);
console.log('Inline capture total byte budget passed');
