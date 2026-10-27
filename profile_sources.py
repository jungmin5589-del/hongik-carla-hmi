"""Verified scene selections; fog retains its independent original source."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
MANIFESTS={'night':'scene-download.json','fog':'long-scene-download.json','congestion':'wide-long-scene-download.json'}

def manifest_name(profile):return MANIFESTS[profile]

def source_id(profile):
    report=json.loads((ROOT/'reports'/manifest_name(profile)).read_text())
    if report['phase']!='download_verified':raise RuntimeError('Verified authorized source required')
    return 'clipgt-'+report['scene']
