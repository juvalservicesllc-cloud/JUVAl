/** Expected observations fixed before first calibration. No browser/redirect/IdP. */
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createServer,createConnection} from 'node:net';
import {once} from 'node:events';
import {MARKER,MAX_BYTES,observeSocket} from './socket_observation_sensor.mjs';

const request=target=>`GET ${target} HTTP/1.1\r\nHost: lab\r\n\r\n`;
const full=request('/synthetic'), marked=request('/synthetic?code='+MARKER);
const partial='GET /synthetic HTTP/1.1\r\nHost: lab';
const forbidden=new Set([18080,5900,5901,6080,6081,9011,9012,9222]);
const waitUntil=async predicate=>{
 const deadline=Date.now()+1500;
 while(!predicate()) {assert(Date.now()<deadline,'FIXTURE_PROGRESS_TIMEOUT');await new Promise(r=>setTimeout(r,2));}
};
async function fixture(t) {
 const sockets=new Set(),clients=new Set(),unclaimed=new Set(),observers=[];
 const server=createServer({allowHalfOpen:true},socket=>{
  socket.pause();sockets.add(socket);unclaimed.add(socket);socket.once('close',()=>sockets.delete(socket));
 });
 const listening=once(server,'listening');server.listen(0,'127.0.0.1');await listening;
 t.after(async()=>{
  const closing=new Promise(resolve=>server.close(resolve));
  for(const o of observers)o.abort();
  for(const client of clients)client.destroy();
  for(const socket of sockets)socket.destroy();
  await closing;
  await Promise.all(observers.map(o=>o.report));
  await waitUntil(()=>sockets.size===0 && clients.size===0);
  assert.equal(server.listening,false);assert.equal(sockets.size,0);assert.equal(clients.size,0);
  assert.equal(unclaimed.size,0,'UNATTRIBUTED_FIXTURE_CONNECTION');
 });
 const address=server.address();
 assert.equal(address.address,'127.0.0.1');assert(!forbidden.has(address.port));
 return async(options={})=>{
  const accepted=once(server,'connection');
  const client=createConnection({host:'127.0.0.1',port:address.port});
  clients.add(client);client.once('close',()=>clients.delete(client));client.on('error',()=>{});
  await once(client,'connect');
  const [socket]=await accepted;
  assert.equal(socket.remoteAddress,'127.0.0.1');assert.equal(socket.remotePort,client.localPort);
  unclaimed.delete(socket);
  const o=observeSocket(socket,{attributed:true,...options});observers.push(o);
  return {client,...o};
 };
}
function expected(bytes,changes={}) {
 return {tcp_connections_accepted:1,application_bytes_received:bytes,
  request_line_recognized:false,header_terminator_seen:false,http_requests_parsed:0,
  marker_observed:false,protocol_failure:false,truncated:false,timed_out:false,
  abnormal_close:false,sensor_error:false,attributed:true,observation_complete:false,
  classification:'INCONCLUSIVE',...changes};
}
const complete={request_line_recognized:true,header_terminator_seen:true,http_requests_parsed:1,
 observation_complete:true,classification:'APPLICATION_BYTES_OBSERVED'};
function verify(actual,wanted) {
 assert.deepEqual(actual,wanted);
 const output=JSON.stringify(actual);
 assert(output.length<1024);assert(!output.includes(MARKER));
 assert(!output.includes('/synthetic'));assert(!output.includes('Host:'));
 for(const [key,value] of Object.entries(actual)) {
  if(key==='classification') assert(['INCONCLUSIVE','APPLICATION_BYTES_OBSERVED',
   'NO_APPLICATION_BYTES_OBSERVED_WITHIN_SENSOR_BOUNDARY'].includes(value));
  else if(typeof value==='number') assert(Number.isInteger(value)&&value>=0&&value<=MAX_BYTES);
  else assert.equal(typeof value,'boolean');
 }
}
async function send(o,parts) {
 let written=0;
 for(const part of parts) {
  o.client.write(part);written+=Buffer.byteLength(part);
  await waitUntil(()=>o.receivedBytes()===written);
 }
 assert.equal(o.client.bytesWritten,written);
 o.client.end();return o.report;
}
test('A: owned empty TCP clean close is a complete receive-side negative',async t=>{
 const o=await(await fixture(t))();o.client.end();
 verify(await o.report,expected(0,{observation_complete:true,
  classification:'NO_APPLICATION_BYTES_OBSERVED_WITHIN_SENSOR_BOUNDARY'}));
});
test('B: one byte differs from zero, incomplete HTTP remains inconclusive',async t=>{
 const o=await(await fixture(t))();verify(await send(o,['G']),expected(1,{truncated:true}));
});
test('C: completed request line is not a parsed complete HTTP request',async t=>{
 const o=await(await fixture(t))();verify(await send(o,[partial]),expected(Buffer.byteLength(partial),
  {request_line_recognized:true,truncated:true}));
});
test('D: marker fragmented across writes and receive boundaries is observed',async t=>{
 const o=await(await fixture(t))();
 const parts=['GET /synthetic?code=',...Array.from(MARKER),' HTTP/1.1\r\nHost: lab\r\n\r\n'];
 verify(await send(o,parts),expected(Buffer.byteLength(marked),{...complete,marker_observed:true}));
});
test('E: complete synthetic HTTP parses independently of raw byte measurement',async t=>{
 const o=await(await fixture(t))();verify(await send(o,[full]),expected(Buffer.byteLength(full),complete));
});
test('F: malformed HTTP is protocol failure, never a successful negative',async t=>{
 const o=await(await fixture(t))();verify(await send(o,['!\r\n\r\n']),expected(5,
  {header_terminator_seen:true,protocol_failure:true}));
});
test('G: reset without payload has incomplete coverage',async t=>{
 const o=await(await fixture(t))();o.client.resetAndDestroy();
 verify(await o.report,expected(0,{abnormal_close:true}));
});
test('H: idle timeout cannot become zero-byte success',async t=>{
 const o=await(await fixture(t))({timeoutMs:50});
 verify(await o.report,expected(0,{timed_out:true,abnormal_close:true}));
});
test('I: sequential sockets do not inherit a prior positive marker',async t=>{
 const connect=await fixture(t);
 const a=await connect();verify(await send(a,[marked]),expected(Buffer.byteLength(marked),{...complete,marker_observed:true}));
 const b=await connect();verify(await send(b,[full]),expected(Buffer.byteLength(full),complete));
});
test('J: interleaved simultaneous sockets cannot assemble a cross-socket marker',async t=>{
 const connect=await fixture(t),a=await connect(),b=await connect();
 const cut=Math.floor(MARKER.length/2),first=MARKER.slice(0,cut),second=MARKER.slice(cut);
 const prefix='GET /synthetic?code=',suffix=' HTTP/1.1\r\nHost: lab\r\n\r\n';
 for(const o of [a,b]) {o.client.write(prefix);await waitUntil(()=>o.receivedBytes()===Buffer.byteLength(prefix));}
 a.client.write(first);await waitUntil(()=>a.receivedBytes()===Buffer.byteLength(prefix+first));
 b.client.write(second);await waitUntil(()=>b.receivedBytes()===Buffer.byteLength(prefix+second));
 a.client.end(suffix);b.client.end(suffix);
 verify(await a.report,expected(Buffer.byteLength(prefix+first+suffix),complete));
 verify(await b.report,expected(Buffer.byteLength(prefix+second+suffix),complete));
});
test('K: unattributed empty clean socket remains inconclusive',async t=>{
 const o=await(await fixture(t))({attributed:false});o.client.end();
 verify(await o.report,expected(0,{attributed:false}));
});
test('L: explicit sensor abort cannot create negative evidence',async t=>{
 const o=await(await fixture(t))();o.abort();
 verify(await o.report,expected(0,{sensor_error:true,abnormal_close:true}));
});
test('M: input limit fails closed with bounded output',async t=>{
 const o=await(await fixture(t))();o.client.write('G'.repeat(MAX_BYTES+1));
 verify(await o.report,expected(MAX_BYTES,{sensor_error:true,abnormal_close:true}));
});
