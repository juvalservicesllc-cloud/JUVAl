/** Synthetic-only receive-side observer. Not an egress/containment mechanism. */
import {createServer} from 'node:http';
import {Duplex} from 'node:stream';

export const MARKER = 'SYNTHETIC_REDIRECT_CODE_SENTINEL';
export const MAX_BYTES = 4096;

// Prefix automaton: retains an index, never a received payload suffix.
function matcher(pattern) {
  const bytes = Buffer.from(pattern);
  const failure = new Array(bytes.length).fill(0);
  for(let i=1,j=0;i<bytes.length;i++) {
    while(j && bytes[i]!==bytes[j]) j=failure[j-1];
    if(bytes[i]===bytes[j]) j++;
    failure[i]=j;
  }
  let index=0;
  return byte => {
    while(index && byte!==bytes[index]) index=failure[index-1];
    if(byte===bytes[index]) index++;
    if(index!==bytes.length) return false;
    index=failure[index-1];
    return true;
  };
}

/** Recognizes only the calibration grammar GET <nonempty ASCII target> HTTP/1.1 CRLF.
 * General HTTP validity is determined independently by Node's HTTP parser.
 */
function requestLine() {
  const start=Buffer.from('GET '), tail=Buffer.from('HTTP/1.1\r\n');
  let stage='prefix', index=0, target=false;
  return byte => {
    if(stage==='done') return true;
    if(stage==='invalid') return false;
    if(stage==='prefix') {
      if(byte!==start[index++]) stage='invalid';
      else if(index===start.length) {stage='target';index=0;}
    } else if(stage==='target') {
      if(byte===32 && target) stage='version';
      else if(byte>=33 && byte<=126) target=true;
      else stage='invalid';
    } else {
      if(byte!==tail[index++]) stage='invalid';
      else if(index===tail.length) stage='done';
    }
    return stage==='done';
  };
}

export function observeSocket(socket, {attributed=false, timeoutMs=2000}={}) {
  if(typeof attributed!=='boolean' || !Number.isInteger(timeoutMs) || timeoutMs<20 || timeoutMs>5000)
    throw new Error('INVALID_SENSOR_CONFIGURATION');
  const r={tcp_connections_accepted:1, application_bytes_received:0,
    request_line_recognized:false, header_terminator_seen:false, http_requests_parsed:0,
    marker_observed:false, protocol_failure:false, truncated:false, timed_out:false,
    abnormal_close:false, sensor_error:false, attributed,
    observation_complete:false, classification:'INCONCLUSIVE'};
  const match=matcher(MARKER), terminator=matcher('\r\n\r\n'), line=requestLine();
  let ended=false, rawClosed=false, parserClosed=false, resolved=false;
  let resolveReport;
  const report=new Promise(resolve=>{resolveReport=resolve;});
  // Unbound HTTP parser over an in-memory Duplex. HTTP responses are discarded;
  // they are never reflected to the network, logs, or evidence output.
  const input=new Duplex({read(){},write(_chunk,_encoding,done){done();}});
  const parser=createServer({maxHeaderSize:MAX_BYTES},(request,response)=>{
    request.on('error',()=>{r.protocol_failure=true;});
    request.on('end',()=>{
      if(request.complete && r.http_requests_parsed<16) r.http_requests_parsed++;
      else r.sensor_error=true;
    });
    request.resume();
    response.end();
  });
  parser.on('clientError',error=>{
    if(error.code==='HPE_INVALID_EOF_STATE') r.truncated=true;
    else r.protocol_failure=true;
    input.destroy(); // No rawPacket/error serialization.
  });
  input.on('error',()=>{r.sensor_error=true;});
  const finish=()=>{
    if(resolved || !rawClosed || !parserClosed) return;
    resolved=true; clearTimeout(deadline);
    if(ended && r.application_bytes_received>0 && !r.http_requests_parsed && !r.protocol_failure)
      r.truncated=true;
    r.observation_complete=ended && r.attributed && !r.protocol_failure && !r.truncated &&
      !r.timed_out && !r.abnormal_close && !r.sensor_error;
    if(r.observation_complete) r.classification=r.application_bytes_received===0 ?
      'NO_APPLICATION_BYTES_OBSERVED_WITHIN_SENSOR_BOUNDARY' : 'APPLICATION_BYTES_OBSERVED';
    resolveReport(Object.freeze({...r}));
  };
  input.on('close',()=>{parserClosed=true;finish();});
  const deadline=setTimeout(()=>{
    r.timed_out=true; socket.destroy(); input.destroy();
  },timeoutMs);
  socket.on('data',chunk=>{
    try {
      if(chunk.length>MAX_BYTES-r.application_bytes_received) {
        r.application_bytes_received=MAX_BYTES; r.sensor_error=true;
        socket.destroy();input.destroy();return;
      }
      r.application_bytes_received+=chunk.length;
      for(const byte of chunk) {
        r.marker_observed=match(byte)||r.marker_observed;
        r.header_terminator_seen=terminator(byte)||r.header_terminator_seen;
        r.request_line_recognized=line(byte)||r.request_line_recognized;
      }
      if(!input.destroyed) input.push(chunk);
    } catch {r.sensor_error=true;socket.destroy();input.destroy();}
  });
  socket.on('end',()=>{ended=true;if(!input.destroyed)input.push(null);socket.end();});
  socket.on('error',()=>{r.abnormal_close=true;});
  socket.on('close',hadError=>{
    rawClosed=true;r.abnormal_close ||= hadError || !ended;
    if(!ended && !input.destroyed)input.destroy();
    finish();
  });
  try {parser.emit('connection',input);socket.resume();}
  catch {r.sensor_error=true;socket.destroy();input.destroy();}
  return {report, receivedBytes:()=>r.application_bytes_received,
    abort:()=>{r.sensor_error=true;socket.destroy();input.destroy();}};
}
