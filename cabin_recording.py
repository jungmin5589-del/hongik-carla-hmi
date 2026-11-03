"""Read-only, allowlisted streaming of a verified public field recording.

The file/manifest remain in the external cache. No audio in Git; no URL or file
name from a request is ever used as a filesystem path.
"""
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

CACHE=Path(__file__).resolve().parent.parent/'cache'/'recorded-cabin'
FILENAME='bigsoundbank-3099.mp3'


@lru_cache(maxsize=1)
def verified():
    record=json.loads((CACHE/'manifest.json').read_text(encoding='utf-8'))
    path=CACHE/FILENAME
    if record['filename']!=FILENAME or record['license']!='CC0-1.0':raise ValueError('Invalid recording provenance')
    if not 1000<path.stat().st_size<16*1024*1024:raise ValueError('Invalid recording size')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:raise ValueError('Recording checksum mismatch')
    return path,record


def catalog():
    try:
        _,r=verified()
        return dict(available=True,url='/api/cabin-audio/drive.mp3',title=r['title'],author=r['author'],
                    license=r['license'],source_url=r['source_url'],recorded_elsewhere=True)
    except (OSError,ValueError,KeyError):return dict(available=False,reason='실제 주행 녹음 파일을 준비해 주세요.')


def stream(handler,head=False):
    try:path,_=verified()
    except (OSError,ValueError,KeyError):handler.send_error(503,'Cabin recording not prepared');return
    size=path.stat().st_size;start,end=0,size-1;partial=False
    header=handler.headers.get('Range')
    if header:
        match=re.fullmatch(r'bytes=(\d*)-(\d*)',header.strip())
        try:
            if not match or not any(match.groups()):raise ValueError()
            a,b=match.groups();start=int(a) if a else max(0,size-int(b));end=min(size-1,int(b)) if a and b else size-1
            if start>=size or start>end or (not a and int(b)==0):raise ValueError()
            partial=True
        except ValueError:
            handler.send_response(416);handler.send_header('Content-Range',f'bytes */{size}')
            handler.send_header('Content-Length','0');handler.end_headers();return
    handler.send_response(206 if partial else 200)
    handler.send_header('Content-Type','audio/mpeg');handler.send_header('Accept-Ranges','bytes')
    handler.send_header('Content-Length',str(end-start+1));handler.send_header('Cache-Control','private, max-age=3600')
    if partial:handler.send_header('Content-Range',f'bytes {start}-{end}/{size}')
    handler.end_headers()
    if head:return
    try:
        with path.open('rb') as source:
            source.seek(start);remaining=end-start+1
            while remaining:
                block=source.read(min(65536,remaining))
                if not block:break
                handler.wfile.write(block);remaining-=len(block)
    except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
