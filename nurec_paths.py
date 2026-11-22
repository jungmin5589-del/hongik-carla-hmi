"""Resolve the separate licensed NuRec installation after an SSD letter changes."""
import os
from pathlib import Path

CODE = Path(__file__).resolve().parent

def data_root():
    configured = os.environ.get('HONGIK_NUREC_ROOT')
    candidates = ([Path(configured)] if configured else []) + [CODE.parent]
    if os.name == 'nt':
        # Do not probe cloud-drive letters: a missing cloud path may block an
        # otherwise local status page on network IO. Other letters use the env
        # override or run directly from that installation's live folder.
        candidates += [Path(f'{drive}:/CARLA-Maps/NuRec-OneScene-20261018') for drive in 'EDF']
    for root in candidates:
        if (root/'reports/scene-download.json').is_file() and (root/'source').is_dir():
            return root.resolve()
    raise FileNotFoundError('NuRec 원본 SSD를 연결하거나 HONGIK_NUREC_ROOT를 지정해 주세요.')

def stored_file(value, root=None):
    root = root or data_root()
    text = str(value).replace('\\', '/')
    marker = '/CARLA-Maps/NuRec-OneScene-20261018/'
    # Prefer this installation, never a stale other drive with the same letter.
    if marker in text:
        candidate = root/text.split(marker, 1)[1]
        if candidate.is_file(): return candidate
    if text.startswith('/mnt/') and len(text)>7 and text[6]=='/':
        text = text[5].upper()+':/'+text[7:]
    candidate = Path(text)
    if candidate.is_file(): return candidate
    raise FileNotFoundError('검증된 NuRec 원본을 찾을 수 없습니다: '+candidate.name)

def official_root():
    configured = os.environ.get('HONGIK_NUREC_OFFICIAL')
    candidates = ([Path(configured)] if configured else [])
    try:candidates.append(data_root()/'source/official-integration')
    except FileNotFoundError:pass
    candidates += [Path(f'{drive}:/CARLA-Build/carla-0.9.16/PythonAPI/examples/nvidia/nurec') for drive in 'EDF']
    for path in candidates:
        if (path/'projection_functions.py').is_file(): return path
    raise FileNotFoundError('별도 CARLA 0.9.16 NuRec 통합 소스가 필요합니다.')

def wsl_path(path):
    path = Path(path).resolve()
    if not path.drive or not path.is_absolute(): raise ValueError('Absolute Windows path required')
    return '/mnt/'+path.drive[0].lower()+'/'+path.as_posix()[3:]
