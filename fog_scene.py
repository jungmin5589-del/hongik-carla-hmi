"""Small fog cast: a stable close-view sedan and the recorded roadside truck."""
import hashlib
import json
from pathlib import Path

# Reuse the already-authorized highway sedan's fixed appearance. The source
# hatchback was reconstructed far away and becomes diffuse when moved close.
LEAD_TRACK_ID='31001'
LEAD_ASSET_NAME='white_sedan'
LEAD_ASSET_GROUND_HEIGHT=.6915195763

def lead_asset_specs():
    folder=Path(__file__).resolve().parent.parent/'source/traffic-assets-temporal-v2'
    record=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))[LEAD_ASSET_NAME]
    asset=folder/record['filename']
    if not asset.is_file():
        raise RuntimeError('Prepare the authorized highway sedan asset before starting fog.')
    with asset.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=record['sha256']:
            raise RuntimeError('The local fog sedan does not match its provenance manifest.')
    return [dict(id=LEAD_TRACK_ID,semantic_class='automobile',
                 asset_id=record['container_path'],size=record['size'])]

CONTEXT_TRACK_IDS=('7','36')
ONSET_SECONDS=10.
BASE_GAP_M=8.
FOG_BUILDUP_SECONDS=5.
EXTINCTION_TIMES=(ONSET_SECONDS,ONSET_SECONDS+FOG_BUILDUP_SECONDS,300.)
EXTINCTION_BETAS=(0.,.20,.20)
