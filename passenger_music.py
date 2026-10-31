"""Original five local tracks, read-only streaming. Audio stays outside Git."""
import re
from pathlib import Path

MUSIC=Path.home()/'Desktop/홍익대/2026 2학기/휴먼 자율주행 인터렉션 디자인/CARLA-YOLO-실습/music'
TRACKS=[
 ('yerin','그건 아마 우리의 잘못은 아닐 거야','백예린','Our love is great','yerin.flac','#d7b99f'),
 ('chet','I Fall In Love Too Easily','Chet Baker','60 Essential Hits · Prince of Cool','chet.flac','#a0b5c1'),
 ('yoo','사랑하기 때문에','유재하','사랑하기 때문에','yoo.mp3','#b4b49a'),
 ('oasis',"Don't Look Back In Anger",'Oasis','(What’s the Story) Morning Glory?','oasis.mp3','#a0a9bd'),
 ('september','September','Earth, Wind & Fire','September','september.mp3','#c1a56b')]

def library():
 return [dict(id=k,title=t,artist=a,album=b,color=c,available=(MUSIC/f).is_file(),url='/media/'+k) for k,t,a,b,f,c in TRACKS]

def stream(handler,key,head=False):
 entry=next((r for r in TRACKS if r[0]==key),None)
 if entry is None or not (MUSIC/entry[4]).is_file():handler.send_error(404);return
 path=MUSIC/entry[4];size=path.stat().st_size;start,end=0,size-1;partial=False
 header=handler.headers.get('Range')
 if header:
  match=re.fullmatch(r'bytes=(\d*)-(\d*)',header.strip())
  try:
   if not match or not any(match.groups()):raise ValueError()
   a,b=match.groups();start=int(a) if a else max(0,size-int(b));end=min(size-1,int(b)) if a and b else size-1
   if start>=size or start>end or (not a and int(b)==0):raise ValueError()
   partial=True
  except ValueError:
   handler.send_response(416);handler.send_header('Content-Range',f'bytes */{size}');handler.send_header('Content-Length','0');handler.end_headers();return
 handler.send_response(206 if partial else 200)
 handler.send_header('Content-Type','audio/flac' if path.suffix=='.flac' else 'audio/mpeg')
 handler.send_header('Accept-Ranges','bytes');handler.send_header('Content-Length',str(end-start+1))
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
