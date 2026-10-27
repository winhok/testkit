import assert from 'node:assert/strict';
import { observeSession } from '../scripts/ego_session.mjs';
const binding = {provider:'ego-lite',session:'7',page:'p1',profile:'default',target:'fixture'};
const oracle = {origin:'https://example.invalid',authenticatedSelector:'#home',loginSelector:'#login'};
let state = {positive:true,login:false};
const page = {label:'p1',url:async()=> 'https://example.invalid/home?token=SECRET',evaluate:async fn=> {
  // Execute the actual browser callback against a minimal DOM seam.
  globalThis.document = {querySelector: selector => state[selector === '#home' ? 'positive' : 'login'] ?
    {getBoundingClientRect:()=>({width:10,height:10})} : null};
  globalThis.getComputedStyle = ()=>({visibility:'visible',display:'block'});
  return fn({authenticatedSelector:'#home',loginSelector:'#login'});
}};
for (const [value, auth] of [[{positive:true,login:false},'authenticated'],[{positive:false,login:true},'required'],
                            [{positive:false,login:false},'unknown'],[{positive:true,login:true},'unknown']]) {
  state=value;
  const observed = await observeSession({spaceId:7},page,binding,oracle);
  assert.equal(observed.authentication,auth);
  assert.equal(observed.target_confirmed,true);
  assert.ok(!JSON.stringify(observed).includes('SECRET'));
}
await assert.rejects(observeSession({spaceId:8},page,binding,oracle),/session-mismatch/);
await assert.rejects(observeSession({spaceId:7},page,binding,{...oracle,origin:'file:///tmp'}),/invalid-oracle/);
page.url=async()=> 'https://sso.example.invalid/';
const originalEvaluate = page.evaluate;
page.evaluate=async()=>{throw new Error('out-of-scope DOM read')};
const foreign = await observeSession({spaceId:7},page,binding,oracle);
assert.equal(foreign.target_confirmed,false);
assert.equal(foreign.authentication,'unknown');
page.evaluate=originalEvaluate;
page.url=async()=>{throw new Error('connection lost')};
await assert.rejects(observeSession({spaceId:7},page,binding,oracle),/connection lost/);
console.log('ego observation adapter: 8 scenarios passed');

const { collectStaticSignals } = await import('../scripts/ego_session.mjs');
const staticPage = {
  url: async()=> 'https://example.invalid/login?token=SECRET',
  evaluate: async fn=> {
    globalThis.document = {querySelectorAll: selector => Array(
      ({form:1,'input[type="password"]':2,'script[src]':3,iframe:1})[selector] || 0).fill({value:'SECRET'})};
    return fn();
  },
};
const signals = await collectStaticSignals(staticPage,['https://example.invalid']);
assert.equal(signals.password_fields,2);
assert.equal(signals.scripts,3);
assert.ok(!JSON.stringify(signals).includes('SECRET'));
assert.ok(signals.limitations.includes('no-anti-bot-verdict'));
await assert.rejects(collectStaticSignals(staticPage,['https://other.example.invalid']),/static-target-unconfirmed/);
console.log('static signals: scope, counts, privacy and inference boundaries passed');
