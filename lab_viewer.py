"""One borderless Surround window, fed by synchronized camera bundles only."""
import io,json,os,threading,time,urllib.request,zipfile
from lab_settings import settings

def monitors():
    if os.name!='nt':return []
    import ctypes
    from ctypes import wintypes
    try:ctypes.windll.user32.SetProcessDPIAware()
    except OSError:pass
    result=[]
    callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HANDLE,wintypes.HANDLE,ctypes.POINTER(wintypes.RECT),wintypes.LPARAM)
    def visit(handle,hdc,rect,param):
        r=rect.contents;result.append([r.left,r.top,r.right-r.left,r.bottom-r.top]);return True
    ctypes.windll.user32.EnumDisplayMonitors(0,0,callback(visit),0)
    return result

def surround_rect(rects):
    # Never choose a normal monitor merely because it is closest in size.
    exact=next((r for r in rects if r[2:]==[5760,1080]),None)
    if exact:return exact
    # Preserve the calibrated viewport on this PC's three 1920x1200 panels.
    taller=next((r for r in rects if r[2:]==[5760,1200]),None)
    return [taller[0],taller[1]+60,5760,1080] if taller else None

def main():
    cfg=settings();preview=os.environ.get('HONGIK_LAB_PREVIEW')=='1';rect=surround_rect(monitors())
    if rect is None and not preview:raise RuntimeError('5760x1080 Surround not detected. Run lab display check; no off-screen window was opened.')
    os.environ['PYGAME_HIDE_SUPPORT_PROMPT']='1'
    os.environ['SDL_VIDEO_WINDOW_POS']='40,60' if preview else f'{rect[0]},{rect[1]}'
    import pygame
    from display_frames import CachedFrame
    pygame.display.init();pygame.font.init();size=(1200,225) if preview else tuple(cfg['display'])
    screen=pygame.display.set_mode(size,pygame.RESIZABLE if preview else pygame.NOFRAME)
    pygame.display.set_caption('Hongik CARLA · Lab Surround'+(' · preview' if preview else ''))
    stop=threading.Event();lock=threading.Lock();latest=[None];last_frame=[-1];token=[''];received=[0.]
    message=pygame.font.Font(None,28).render('Waiting for live camera views',True,(235,235,235))
    def receive():
        while not stop.is_set():
            try:
                with urllib.request.urlopen('http://127.0.0.1:8774/rig/bundle?after='+str(last_frame[0])+'&token='+token[0],timeout=5) as response:
                    if response.status==204:continue
                    data=response.read()
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    meta=json.loads(z.read('frame.json'));frame=meta['frame'];parts=[z.read(v+'.jpg') for v in ('left','center','right')]
                with lock:latest[0]=parts;last_frame[0]=frame;token[0]=meta['token'];received[0]=time.monotonic()
            except (OSError,ValueError,zipfile.BadZipFile,KeyError):
                stop.wait(.5)
    threading.Thread(target=receive,daemon=True).start();caches=[CachedFrame() for _ in range(3)];clock=pygame.time.Clock()
    try:
        while not stop.is_set():
            for event in pygame.event.get():
                if event.type==pygame.QUIT or event.type==pygame.KEYDOWN and event.key==pygame.K_ESCAPE:stop.set()
            screen.fill((8,10,14));w,h=screen.get_size();panel=w//3
            with lock:parts=latest[0];fresh=time.monotonic()-received[0]<3
            if parts:
                for i,jpeg in enumerate(parts):
                    surf=caches[i].surface(jpeg,(panel,h))
                    if surf:screen.blit(surf,(i*panel+(panel-surf.get_width())//2,(h-surf.get_height())//2))
            if not fresh:
                shade=pygame.Surface((w,h));shade.set_alpha(170);screen.blit(shade,(0,0));screen.blit(message,((w-message.get_width())//2,(h-message.get_height())//2))
            pygame.display.flip();clock.tick(cfg['fps'])
    finally:
        stop.set();pygame.quit()
        try:
            req=urllib.request.Request('http://127.0.0.1:8774/control',data=b'{"mode":"paused"}',headers={'Content-Type':'application/json'})
            urllib.request.urlopen(req,timeout=2).close()
        except OSError:pass
