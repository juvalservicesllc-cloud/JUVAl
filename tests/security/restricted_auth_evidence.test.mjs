import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Controller, evidence, normalizedPath, validRequest} from '../../tools/restricted_auth_evidence.mjs';
const sentinel = 'SYNTHETIC_PASSWORD_SENTINEL';
const origin = 'http://127.0.0.1:18081';
test('output schema and path allowlist never reflect arbitrary input', () => {
  for (const p of ['/login', '/challenge', '/callback'])
    assert.equal(normalizedPath(origin + p + '?code=' + sentinel + '#' + sentinel, origin), p);
  for (const u of [origin + '/' + sentinel, 'https://elsewhere/login', 'file:///login',
    origin + '/%6cogin', origin + '/login/' + sentinel, 'invalid', 'http://user:pass@127.0.0.1:18081/login'])
    assert.equal(normalizedPath(u, origin), null);
  assert.deepEqual(evidence(sentinel, sentinel), {status: 'REJECTED', path: null});
});
test('only exact request schemas accepted', () => {
  for (const op of ['evaluate','snapshot','console','network','cookies','storageState','screenshot','trace','navigate'])
    assert.equal(validRequest({op, value: sentinel}), false);
  for (const r of [null, [], {}, {op:'observe', extra:sentinel}, {op:'visit', state:'__proto__'}, {op:'visit', state:sentinel}])
    assert.equal(validRequest(r), false);
  assert.equal(validRequest({op:'visit',state:'login'}),true);
});
test('exceptions and closed lifecycle fail without reflecting browser data', async () => {
  const c = new Controller({close:async()=>{}}, {goto:async()=>{throw new Error(sentinel)}, url:()=>origin+'/callback?'+sentinel}, origin);
  assert.deepEqual(await c.request({op:'visit',state:'login'}),evidence('FAILED'));
  assert.deepEqual(await c.request({op:'observe'}),evidence('OBSERVED','/callback'));
  assert.deepEqual(await c.request({op:'close'}),evidence('CLOSED'));
  assert.deepEqual(await c.request({op:'observe'}),evidence('REJECTED'));
});
test('invalid operations cannot invoke browser methods and cleanup failure is bounded', async () => {
  let calls=0;
  const c=new Controller({close:async()=>{throw new Error(sentinel)}},
    {goto:async()=>{calls++},url:()=>{calls++;return origin+'/'+sentinel}},origin);
  assert.deepEqual(await c.request({op:'evaluate',value:sentinel}),evidence('REJECTED'));
  assert.equal(calls,0);
  assert.deepEqual(await c.request({op:'observe'}),evidence('REJECTED'));
  assert.deepEqual(await c.close(),evidence('FAILED'));
});
