"""Read-only, bounded P4 asset timing; no browser or file protocol mutations."""
from pathlib import Path
import argparse, collections, datetime, hashlib, json, socket, time, zlib

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'build-artifacts/p4-tcp-heartbeat-assets/assets-manifest.json'

def stats(values):
    ordered = sorted(values)
    if not ordered: return {}
    return {'min': round(ordered[0], 3), 'p50': round(ordered[len(ordered)//2], 3),
            'p95': round(ordered[min(len(ordered)-1, int(len(ordered)*.95))], 3),
            'max': round(ordered[-1], 3)}

def measure(host, asset):
    begin = time.perf_counter(); arrivals = []; chunks = []; data = bytearray(); buf = bytearray()
    limit = begin + 90
    with socket.create_connection((host, 80), timeout=5) as sock:
        connected = time.perf_counter(); sock.settimeout(5)
        sock.sendall(('GET /'+asset['path']+' HTTP/1.1\r\nHost: '+host+
                      '\r\nAccept-Encoding: gzip\r\nConnection: close\r\n\r\n').encode())
        def recv():
            assert time.perf_counter() < limit, 'total 90s bound'
            block = sock.recv(65536); assert block, 'premature EOF'
            arrivals.append((time.perf_counter()-begin, len(block)))
            buf.extend(block)
        def line(maximum=128):
            while b'\r\n' not in buf:
                assert len(buf) <= maximum; recv()
            end = buf.index(b'\r\n'); assert end <= maximum
            result = bytes(buf[:end]); del buf[:end+2]; return result
        while b'\r\n\r\n' not in buf:
            assert len(buf) < 16384; recv()
        end = buf.index(b'\r\n\r\n'); assert end<=16384
        raw = bytes(buf[:end]); del buf[:end+4]
        lines = raw.decode('ascii').split('\r\n'); assert lines[0].split()[1] == '200'
        headers = dict((k.lower(),v.strip()) for k,v in (x.split(':',1) for x in lines[1:]))
        assert headers.get('transfer-encoding') == 'chunked', headers
        header_time = time.perf_counter()
        while True:
            length = int(line().split(b';')[0], 16); assert 0 <= length <= 65536
            if not length:
                assert line() == b''; break
            assert len(data)+length <= asset['flash_bytes']
            while len(buf) < length + 2: recv()
            assert buf[length:length+2] == b'\r\n'
            data.extend(buf[:length]); del buf[:length+2]
            assert len(data) <= asset['flash_bytes']
            chunks.append((time.perf_counter()-begin, length))
        received = time.perf_counter()
    assert len(data) == asset['flash_bytes']
    if headers.get('content-encoding') == 'gzip':
        decoder=zlib.decompressobj(16+zlib.MAX_WBITS)
        decoded=decoder.decompress(data,asset['bytes']+1)
        assert decoder.eof and not decoder.unconsumed_tail and not decoder.unused_data
    else: decoded=bytes(data)
    verified = time.perf_counter()
    assert len(decoded) == asset['bytes'] and hashlib.sha256(decoded).hexdigest() == asset['sha256']
    return {'path':asset['path'], 'compressed_bytes':len(data), 'decoded_bytes':len(decoded), 'hash_match':True,
            'tcp_ms':round((connected-begin)*1000,3), 'headers_ms':round((header_time-begin)*1000,3),
            'seconds':round(received-begin,6), 'body_KiB_s':round(len(data)/1024/(received-header_time),3),
            'decode_ms':round((verified-received)*1000,3), 'body_chunk_sizes':dict(collections.Counter(n for t,n in chunks)),
            'receive_gap_ms':stats([(b[0]-a[0])*1000 for a,b in zip(arrivals,arrivals[1:])]),
            'chunk_gap_ms':stats([(b[0]-a[0])*1000 for a,b in zip(chunks,chunks[1:])]),
            'arrivals':[[round(t,6),n] for t,n in arrivals], 'chunks':[[round(t,6),n] for t,n in chunks]}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True); ap.add_argument('--host',required=True)
    ap.add_argument('--manifest',type=Path,default=MANIFEST)
    ap.add_argument('--paths',nargs='+',default=['gp_wasm.js','gp_wasm.wasm','gp_wasm.data']); args=ap.parse_args()
    target=Path(args.output).resolve(); assert not target.exists(), 'Inspect existing result before a new measurement'
    target.parent.mkdir(parents=True,exist_ok=True)
    manifest=json.loads(args.manifest.read_text()); report={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'SD_written':False, 'settings_written':False, 'measurements':[]}
    try:
        for path in args.paths:
            asset=next(a for a in manifest['assets'] if a['path']==path)
            item=measure(args.host,asset); report['measurements'].append(item)
            target.write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps({k:v for k,v in item.items() if k not in ('arrivals','chunks')}),flush=True)
        report['result']='PASS'
    except BaseException as error:
        report.update(result='NOT_COMPLETED',error_type=type(error).__name__); raise
    finally: target.write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__': main()
