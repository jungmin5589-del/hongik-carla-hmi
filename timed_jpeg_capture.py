"""Capture existing RGB frames with arrival timing; encode after the drive."""
import hashlib
import json
import subprocess
import threading
import time
import urllib.request


class TimedJpegCapture:
    def __init__(self,folder):
        self.folder=folder
        (folder/'frames').mkdir()
        self.frames=[];self.errors=[]
        self.stopped=threading.Event();self.first=threading.Event()
        self.started=time.monotonic()
        self.worker=threading.Thread(target=self.collect,daemon=True)

    def collect(self):
        last=None
        try:
            with urllib.request.urlopen('http://127.0.0.1:8774/stream',timeout=20) as stream:
                while not self.stopped.is_set():
                    line=stream.readline()
                    if not line:raise RuntimeError('RGB stream ended.')
                    if not line.startswith(b'--frame'):continue
                    headers={}
                    while True:
                        line=stream.readline()
                        if line in (b'\r\n',b'\n'):break
                        key,value=line.decode('ascii').split(':',1);headers[key.lower()]=value.strip()
                    size=int(headers['content-length'])
                    if not 0<size<20000000:raise RuntimeError('Unexpected JPEG size.')
                    data=stream.read(size)
                    if self.stopped.is_set():break
                    if len(data)!=size:raise RuntimeError('Truncated JPEG.')
                    digest=hashlib.sha256(data).hexdigest()
                    if digest==last:continue
                    name='frames/%06d.jpg'%len(self.frames)
                    (self.folder/name).write_bytes(data)
                    self.frames.append(dict(file=name,time_s=time.monotonic()-self.started))
                    self.first.set();last=digest
        except Exception as error:
            self.errors.append(str(error));self.first.set()

    def start(self):
        self.worker.start()
        if not self.first.wait(15) or not self.frames or self.errors:raise RuntimeError(str(self.errors))

    def stop(self):
        self.ended=time.monotonic()-self.started
        self.stopped.set();self.worker.join(21)
        (self.folder/'capture-frames.json').write_text(json.dumps(self.frames),encoding='utf-8')
        if self.errors or self.worker.is_alive() or len(self.frames)<3:raise RuntimeError('Incomplete RGB capture: '+str(self.errors))

    def encode(self,ffmpeg,video):
        expected=self.ended-self.frames[0]['time_s']
        lines=['ffconcat version 1.0']
        for i,frame in enumerate(self.frames):
            end=self.frames[i+1]['time_s'] if i+1<len(self.frames) else self.ended
            lines += ["file '"+frame['file']+"'",'option framerate 1000','duration '+str(max(.001,end-frame['time_s']))]
        lines += ["file '"+self.frames[-1]['file']+"'",'option framerate 1000']
        concat=self.folder/'frames.ffconcat';concat.write_text('\n'.join(lines)+'\n',encoding='utf-8')
        with (self.folder/'encode.log').open('w',encoding='utf-8') as log:
            subprocess.run([ffmpeg,'-hide_banner','-loglevel','warning','-n','-f','concat','-safe','0','-i',str(concat),
                '-an','-c:v','libx264','-threads','2','-filter_threads','1','-preset','veryfast','-crf','18',
                '-pix_fmt','yuv420p','-vf','fps=30','-t',str(expected),'-movflags','+faststart',str(video)],
                stdout=log,stderr=subprocess.STDOUT,check=True)
