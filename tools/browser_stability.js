/* SPDX-License-Identifier: MIT
 * Paste this helper into the supported CUA REPL, then pass the existing board
 * tab and its documented cdp capability. It uses no filesystem or alternate
 * browser automation. The caller must authorize discarding this disposable
 * editor workspace; save any original project metadata before testing.
 */
async function captureFreshEditor(tab, cdp, label, {discardDisposableProject = false} = {}) {
  if (!discardDisposableProject) throw new Error('Save the editor project and authorize a disposable reload first');
  const methods = ['Network.requestWillBeSent', 'Network.responseReceived',
    'Network.loadingFinished', 'Network.loadingFailed'];
  const started = Date.now();
  await cdp.send('Network.enable');
  // GP installs an unconditional leave-page warning. The in-app browser cancels
  // it automatically. Remove it only on this disposable old document; the new
  // page reinstates the original handler. This is not a browser security warning.
  await cdp.send('Runtime.evaluate', {expression:'window.onbeforeunload=null',returnByValue:true});
  let cursor = (await cdp.readEvents({methods})).cursor;
  const events = [], pending = new Set(), requests = new Map(), finished = new Set();
  let truncated = false, lastActivity = Date.now();
  await cdp.send('Page.reload', {ignoreCache:true});
  while (Date.now() - started < 45000) {
    const batch = await cdp.readEvents({afterSequence:cursor, methods, limit:1000, timeoutMs:250});
    cursor = batch.cursor;
    truncated ||= batch.truncated;
    events.push(...batch.events);
    if (batch.events.length) lastActivity = Date.now();
    for (const event of batch.events) {
      const {method, params} = event;
      if (method === 'Network.requestWillBeSent') {
        requests.set(params.requestId, params.request.url);
        pending.add(params.requestId);
      }
      if (method === 'Network.loadingFinished' || method === 'Network.loadingFailed') {
        pending.delete(params.requestId);
        const url = requests.get(params.requestId);
        if (url) finished.add(new URL(url).pathname);
      }
    }
    // Drain without Runtime.evaluate during initialization: GP can block the
    // main thread long enough for the CDP event ring to overflow otherwise.
    if (!batch.hasMore && finished.has('/img/icon-zoom-in--16x16.svg') &&
        pending.size === 0 && Date.now() - lastActivity > 1200) break;
  }
  const evaluation = await cdp.send('Runtime.evaluate', {
    expression:'JSON.stringify({ready:!!document.getElementById("board-status")&&document.body.textContent.includes("Waveshare RLCD 4.2"),resources:[...performance.getEntriesByType("navigation"),...performance.getEntriesByType("resource")].map(e=>({name:e.name,status:e.responseStatus,responseEnd:e.responseEnd,duration:e.duration,bytes:e.decodedBodySize}))})',
    returnByValue:true
  });
  const page = JSON.parse(evaluation.result.value);
  const responses = events.filter(e => e.method === 'Network.responseReceived');
  const failures = events.filter(e => e.method === 'Network.loadingFailed').map(e => ({
    path:new URL(requests.get(e.params.requestId)).pathname, error:e.params.errorText
  }));
  const errors = (await tab.dev.logs({levels:['warn','error'],limit:100}))
    .filter(e => Date.parse(e.timestamp) >= started).map(e => e.message);
  const origins = [...new Set(page.resources.map(r => new URL(r.name).origin))];
  const required = ['/gp_wasm.js','/gp_wasm.data','/gp_wasm.wasm','/translations/en.po',
    '/img/icon-start--24x24.svg','/img/icon-stop--24x24.svg','/img/icon-zoom-in--16x16.svg'];
  const paths = new Set(page.resources.map(r => new URL(r.name).pathname));
  const missing = required.filter(p => !paths.has(p));
  const result = page.ready && !missing.length && !failures.length && !errors.length &&
    !truncated && pending.size === 0 && requests.size >= 39 && responses.length === requests.size &&
    page.resources.every(r => r.status === 200 && r.responseEnd > 0) && origins.length === 1 &&
    origins[0] === new URL(await tab.url()).origin ? 'PASS' : 'FAIL';
  return {label, result, ready:page.ready, elapsed_ms:Date.now()-started,
    requests:requests.size, responses:responses.length, resource_timing_entries:page.resources.length,
    truncated, pending:pending.size, failures, javascript_errors:errors, origins,
    resource_timing:page.resources.map(r => ({path:new URL(r.name).pathname,status:r.status,
      duration_ms:Math.round(r.duration),bytes:r.bytes}))};
}
