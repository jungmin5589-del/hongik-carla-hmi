"""Offline preview from an actual private native range hint; not live evidence."""
import json,uuid
from pathlib import Path
import numpy as np,torch
from PIL import Image
from range_transport import compose_native_fog
ROOT=Path(__file__).resolve().parent
source=ROOT/'validation/fog-depth-fa7540b4'
with np.load(source/'ranges.npz') as data:distance=torch.from_numpy(data['ranges'].copy());directions=torch.from_numpy(data['rays'].astype(np.float32))
color=torch.from_numpy(np.asarray(Image.open(source/'clear.jpg').convert('RGB').resize((240,135)),dtype=np.float32)/255.)
alpha=(distance<500).float();rays=torch.cat((torch.zeros_like(directions),directions),dim=-1)
folder=ROOT/'validation'/('fog-geometric-preview-'+uuid.uuid4().hex[:8]);folder.mkdir()
for beta in [.025,.085,.18]:
    result=compose_native_fog(color,distance*alpha,alpha,beta,65.,rays)
    image=Image.fromarray(np.uint8(np.clip(result.numpy()*255,0,255))).resize((1280,720),Image.Resampling.BICUBIC)
    image.save(folder/(str(beta)+'.jpg'))
(folder/'result.json').write_text(json.dumps(dict(actual_live=False,native_range_source=str(source),resolution=[240,135],upscaled_preview=True)))
print(str(folder))
