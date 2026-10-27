"""Record the existing live JPEG feed and real elapsed time to a private MP4.

Starts one complete route without selecting a response. No screen, microphone,
new render model, interpolation, or simulation speed changes are involved.
"""
import hashlib
import io
import json
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from PIL import Image
from benchmark_fps30 import require_memory

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / 'recording-tools'))
import imageio_ffmpeg

BASE = 'http://127.0.0.1:8774'


def state():
    with urllib.request.urlopen(BASE + '/state', timeout=5) as response:
        return json.load(response)


def control(body):
    request = urllib.request.Request(BASE + '/control', data=json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(request, timeout=5):
        pass


def main():
    initial = state()
    if initial.get('phase') != 'live' or initial.get('error'):
        raise RuntimeError('The existing live renderer is not ready.')
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    folder = ROOT.parent / 'recordings' / ('full-drive-' + time.strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(3))
    folder.mkdir(parents=True, exist_ok=False)
    images = folder / 'frames'
    images.mkdir()
    (folder / 'initial-state.json').write_text(json.dumps(initial, indent=2), encoding='utf-8')
    control({'reset': True})
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        ready = state()
        if (ready['scenario']['session'] != initial['scenario']['session']
                and ready['scenario']['elapsed_s'] == 0 and ready['mode'] == 'paused'):
            break
        time.sleep(.2)
    else:
        raise RuntimeError('Could not reset to the start of the route.')
    session = ready['scenario']['session']
    # Wait for a frame generated after resetting, rather than a previous-session JPEG.
    reset_frame = ready.get('frames', 0)
    deadline = time.monotonic() + 15
    while state().get('frames', 0) <= reset_frame:
        if time.monotonic() > deadline:
            raise RuntimeError('The start frame did not arrive.')
        time.sleep(.2)

    frames, capture_errors = [], []
    stopped, first_frame = threading.Event(), threading.Event()
    began = time.monotonic()

    def collect():
        last_hash = None
        try:
            with urllib.request.urlopen(BASE + '/stream', timeout=12) as stream:
                while not stopped.is_set():
                    line = stream.readline()
                    if not line:
                        raise RuntimeError('Live video stream ended before recording stopped.')
                    if not line.startswith(b'--frame'):
                        continue
                    headers = {}
                    while True:
                        line = stream.readline()
                        if line in (b'\r\n', b'\n'):
                            break
                        if not line:
                            raise RuntimeError('Incomplete JPEG headers.')
                        key, value = line.decode('ascii').split(':', 1)
                        headers[key.lower()] = value.strip()
                    size = int(headers['content-length'])
                    if not 0 < size < 20_000_000:
                        raise RuntimeError('Unexpected JPEG length.')
                    data = stream.read(size)
                    if len(data) != size:
                        raise RuntimeError('Incomplete JPEG frame.')
                    digest = hashlib.sha256(data).hexdigest()
                    if digest == last_hash:
                        continue
                    if not frames:
                        with Image.open(io.BytesIO(data)) as image:
                            if image.size != (initial['width'], initial['height']):
                                raise RuntimeError('Recording resolution changed.')
                            image.verify()
                    last_hash = digest
                    name = f'frames/{len(frames):06d}.jpg'
                    (folder / name).write_bytes(data)
                    frames.append(dict(file=name, time_s=time.monotonic() - began, sha256=digest))
                    first_frame.set()
        except Exception as error:
            capture_errors.append(type(error).__name__ + ': ' + str(error))
            first_frame.set()

    worker = threading.Thread(target=collect, daemon=True)
    worker.start()
    finish = None
    try:
        if not first_frame.wait(15) or not frames or capture_errors:
            raise RuntimeError('No valid first video frame: ' + '; '.join(capture_errors))
        time.sleep(1.5)
        control({'mode': 'auto'})
        print(json.dumps(dict(event='recording_started',folder=str(folder),width=initial['width'],height=initial['height'])), flush=True)
        next_progress = 0.
        with (folder / 'drive-state.jsonl').open('w', encoding='utf-8', buffering=1) as trace:
            deadline = time.monotonic() + 600
            while time.monotonic() < deadline:
                require_memory()
                current = state()
                scenario = current['scenario']
                trace.write(json.dumps(dict(recording_s=time.monotonic()-began,state=current))+'\n')
                if scenario['session'] != session:
                    raise RuntimeError('The session was reset during recording; preserve the partial capture.')
                if current.get('error') or current.get('phase') == 'error' or capture_errors:
                    raise RuntimeError('Live capture failed: ' + str(current.get('error') or capture_errors))
                elapsed = scenario['elapsed_s']
                if elapsed >= next_progress:
                    print(json.dumps(dict(event='recording',elapsed_s=round(elapsed,1),captured_images=len(frames))),flush=True)
                    next_progress = elapsed + 15
                if scenario['completed']:
                    finish = current
                    time.sleep(5)
                    break
                time.sleep(.5)
            else:
                raise RuntimeError('Full route did not finish within the recording limit.')
    finally:
        control({'mode': 'paused'})
        stopped.set()
        worker.join(15)
        (folder / 'capture-frames.json').write_text(json.dumps(frames, indent=2), encoding='utf-8')
        if finish:
            (folder / 'finish-state.json').write_text(json.dumps(finish, indent=2), encoding='utf-8')
    if worker.is_alive() or capture_errors or len(frames) < 3:
        raise RuntimeError('Recording was incomplete: ' + str(capture_errors))
    full_route = finish['scenario']['completion_reason'] == 'route_end'
    capture_end = time.monotonic() - began
    expected = capture_end - frames[0]['time_s']
    lines = ['ffconcat version 1.0']
    for index, frame in enumerate(frames):
        end = frames[index+1]['time_s'] if index+1 < len(frames) else capture_end
        lines += ["file '" + frame['file'] + "'", 'option framerate 1000',
                  'duration ' + str(max(.001,end-frame['time_s']))]
    lines += ["file '" + frames[-1]['file'] + "'", 'option framerate 1000']
    concat = folder / 'frames.ffconcat'
    concat.write_text('\n'.join(lines)+'\n', encoding='utf-8')
    output = folder / ('NuRec-full-drive-540p.mp4' if initial['height']==540 else 'NuRec-full-drive.mp4')
    command = [ffmpeg,'-hide_banner','-loglevel','warning','-n','-f','concat','-safe','0','-i',str(concat),
               '-an','-c:v','libx264','-threads','2','-filter_threads','1',
               '-preset','veryfast','-crf','18','-pix_fmt','yuv420p',
               '-vf','fps=30','-t',str(expected),'-movflags','+faststart',str(output)]
    with (folder/'encode.log').open('w',encoding='utf-8') as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
    inspection = subprocess.run([ffmpeg,'-hide_banner','-i',str(output)],capture_output=True,text=True)
    (folder/'video-inspection.txt').write_text(inspection.stderr,encoding='utf-8')
    match = re.search(r'Duration: (\d+):(\d+):([\d.]+)',inspection.stderr)
    if not match or 'Video: h264' not in inspection.stderr:
        raise RuntimeError('The resulting MP4 did not report valid H.264 video.')
    hours,minutes,seconds=map(float,match.groups())
    duration=hours*3600+minutes*60+seconds
    if abs(duration-expected)>1.5:
        raise RuntimeError('Video duration differs from the real capture timeline.')
    decoded=subprocess.run([ffmpeg,'-v','error','-i',str(output),'-f','null','-'],capture_output=True,text=True)
    if decoded.returncode or decoded.stderr.strip():
        raise RuntimeError('The resulting video did not decode cleanly: '+decoded.stderr)
    shutil.copy2(folder/frames[len(frames)//2]['file'],folder/'preview.jpg')
    # Keep the app ready for the user's next trial, after preserving the ending.
    control({'reset':True})
    result=dict(video=str(output),preview=str(folder/'preview.jpg'),full_route_completed=full_route,
                completion_reason=finish['scenario']['completion_reason'],duration_s=duration,
                resolution=[initial['width'],initial['height']],silent=True,unique_images=len(frames),
                timing='original wall-clock frame arrival; repeated output frames; no interpolation',
                decoded_cleanly=True,sha256=hashlib.file_digest(output.open('rb'),'sha256').hexdigest())
    (folder/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(event='recording_complete',**result)),flush=True)
    if not full_route:
        raise RuntimeError('A response ended the run early; this file is not a full-route recording.')
    return result


if __name__ == '__main__':
    main()
