"""Large resizable driving display. Subscribes to existing frames; no GPU model."""
import json
import math
import os
import threading
import time
import urllib.request

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import pygame
from display_frames import CachedFrame, mjpeg_frames

BASE = 'http://127.0.0.1:8774'
stop = threading.Event()
lock = threading.Lock()
latest = None
state = {}
error = ''


def control(body):
    try:
        req = urllib.request.Request(BASE+'/control', data=json.dumps(body).encode(),
            headers={'Content-Type':'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=2):
            pass
    except OSError:
        pass


def reader():
    global latest, error
    while not stop.is_set():
        try:
            with urllib.request.urlopen(BASE+'/stream', timeout=8) as response:
                for jpeg in mjpeg_frames(response):
                    with lock:
                        latest = jpeg; error = ''
                    if stop.is_set():
                        return
        except (OSError, ValueError, KeyError):
            error = '주행 영상 연결 중…'
        stop.wait(.5)


def state_reader():
    global state
    while not stop.is_set():
        try:
            with urllib.request.urlopen(BASE+'/state', timeout=3) as response:
                state = json.load(response)
        except (OSError, ValueError):
            pass
        stop.wait(.4)


def main():
    pygame.display.init(); pygame.font.init()
    desktop = pygame.display.get_desktop_sizes()[0]
    size = (min(1600, desktop[0]-80), min(900, desktop[1]-140))
    screen = pygame.display.set_mode(size, pygame.RESIZABLE)
    pygame.display.set_caption('NuRec CARLA · Driving Display')
    font_path = 'C:/Windows/Fonts/malgun.ttf'
    font = pygame.font.Font(font_path, 18)
    threading.Thread(target=reader, daemon=True).start()
    threading.Thread(target=state_reader, daemon=True).start()
    clock = pygame.time.Clock()
    fullscreen = False
    cache = CachedFrame()
    last_info = None; text = bg = None
    last_crash = None; impact_until = 0.
    last_alert = ''; alert_surface = None
    try:
        while not stop.is_set():
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    control({'mode':'paused'}); stop.set()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_F11 or (event.key == pygame.K_ESCAPE and fullscreen):
                        fullscreen = not fullscreen
                        screen = pygame.display.set_mode(desktop if fullscreen else size,
                            pygame.FULLSCREEN if fullscreen else pygame.RESIZABLE)
                    elif event.key == pygame.K_SPACE:
                        control({'mode':'auto' if state.get('mode')=='paused' else 'paused'})
                elif event.type == pygame.VIDEORESIZE and not fullscreen:
                    size = event.size
            with lock:
                jpeg = latest
            screen.fill((5,7,10))
            w,h = screen.get_size()
            sc=state.get('scenario',{});crash=sc.get('crash',{})
            crash_key=(sc.get('session'),crash.get('phase'))
            if (last_crash is not None and last_crash[0]==crash_key[0] and last_crash!=crash_key
                    and crash.get('primary_collision_verified')
                    and crash.get('phase') in ('primary_impact','secondary_impact')):
                impact_until=time.monotonic()+.3
            last_crash=crash_key
            shake=max(0.,impact_until-time.monotonic())
            offset=round(6*math.sin(shake*110)*min(1.,shake*4))
            scaled = cache.surface(jpeg, (w,h))
            if scaled:
                screen.blit(scaled,((w-scaled.get_width())//2+offset,(h-scaled.get_height())//2))
            if shake:pygame.draw.rect(screen,(175,55,48),screen.get_rect(),width=7)
            alert=(sc.get('outcome',{}).get('message') if sc.get('completed') else sc.get('feedback','')) if sc.get('action')=='overtake' else ''
            if alert!=last_alert:
                alert_surface=font.render(alert,True,(255,240,235)) if alert else None
                last_alert=alert
            if alert_surface:
                box=pygame.Rect(18,18,min(w-36,alert_surface.get_width()+28),46)
                pygame.draw.rect(screen,(75,27,29),box,border_radius=9)
                screen.blit(alert_surface,(32,31))
            info = error or f"{state.get('width','—')} × {state.get('height','—')}   ·   {round(state.get('speed_kph',0))} km/h   ·   {'일시정지' if state.get('mode')=='paused' else '주행 중'}"
            if info != last_info:
                text = font.render(info+'     F11 전체 화면 · Space 시작/정지',True,(230,233,240))
                bg = pygame.Surface((text.get_width()+28,40),pygame.SRCALPHA); bg.fill((12,16,23,190))
                last_info = info
            screen.blit(bg,(18,h-58));screen.blit(text,(32,h-50))
            pygame.display.flip();clock.tick(30)
    finally:
        stop.set();pygame.quit()


if __name__ == '__main__':
    main()
