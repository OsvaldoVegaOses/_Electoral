// Fixed-destination laboratory ingress. No access logs, dynamic targets or CONNECT proxy.
const http = require('node:http');
const host = process.env.POC_UPSTREAM;
if (!['revote', 'single'].includes(host)) throw new Error('Invalid laboratory upstream');
http.createServer((request, response) => {
  if (request.method === 'CONNECT' || !request.url.startsWith('/')) {
    response.writeHead(400); response.end(); return;
  }
  const fail = () => { if (!response.writableEnded) { response.writeHead(502); response.end(); } };
  let incomingResponse;
  const upstream = http.request({ hostname: host, port: 8001, path: request.url,
    method: request.method, headers: { ...request.headers, connection: 'close' }, agent: false }, incoming => {
    incomingResponse = incoming;
    const chunks = []; let size = 0;
    incoming.on('data', chunk => { size += chunk.length; if (size > 32 * 1024 * 1024) upstream.destroy(); else chunks.push(chunk); });
    incoming.on('error', fail);
    incoming.on('end', () => {
      if (response.writableEnded) return;
      const body = Buffer.concat(chunks);
      const headers = { ...incoming.headers, 'content-length': String(body.length) };
      delete headers['transfer-encoding']; delete headers.connection; delete headers['keep-alive'];
      response.writeHead(incoming.statusCode, headers); response.end(body);
    });
  });
  upstream.setTimeout(15000, () => upstream.destroy());
  upstream.on('error', error => {
    // The pinned Ocsigen/Cohttp bridge appends a chunk terminator after a complete
    // Content-Length response. Accept only that exact five-byte compatibility case.
    const tail = error.rawPacket?.subarray(error.bytesParsed);
    if (error.code === 'HPE_INVALID_CONSTANT' && incomingResponse?.complete &&
        tail?.equals(Buffer.from('0\r\n\r\n'))) return;
    fail();
  });
  response.on('error', () => upstream.destroy());
  request.on('aborted', () => upstream.destroy());
  request.pipe(upstream);
}).listen(8000, '0.0.0.0');
