"""Configure this portable bundle; never replace the lab environment."""
import argparse,json,subprocess,sys,uuid,shutil,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def prepare_engine(root,bundle):
    root=root.resolve();bundle=bundle.resolve();archive=bundle/'CARLA_0.9.16.zip'
    if root!=(bundle/'CARLA_0.9.16').resolve():
        if not (root/'CarlaUE4.exe').is_file():raise RuntimeError('Selected existing engine not found')
        return
    if not (root/'.hongik-engine-ready').is_file() and archive.is_file():
        if root.exists() and any(root.iterdir()) and not (root/'.hongik-engine-extracting').is_file():raise RuntimeError('Existing engine folder left untouched; extract the bundle into a fresh folder')
        if shutil.disk_usage(root.parent).free<20*1024**3:raise RuntimeError('Extract on an internal SSD with at least 20 GiB free')
        print('Extracting the separate CARLA engine; please wait...',flush=True);root.mkdir(exist_ok=True)
        (root/'.hongik-engine-extracting').write_text('Owned portable extraction',encoding='utf-8')
        with zipfile.ZipFile(archive) as z:
            for item in z.infolist():
                destination=(root/item.filename).resolve()
                if not destination.is_relative_to(root):raise RuntimeError('Invalid engine archive path')
                z.extract(item,root)
        (root/'.hongik-engine-ready').write_text('CARLA 0.9.16; archive CRC checked while extracting',encoding='utf-8')
        (root/'.hongik-engine-extracting').unlink()

def main():
    p=argparse.ArgumentParser();p.add_argument('--carla-root',type=Path);args=p.parse_args()
    from lab_settings import settings
    cfg=settings();root=(args.carla_root or ROOT.parent/'CARLA_0.9.16').resolve()
    prepare_engine(root,ROOT.parent)
    if not (root/'CarlaUE4.exe').is_file():raise RuntimeError('Extract the full portable bundle, including CARLA_0.9.16.zip')
    import carla
    if not carla.Client('127.0.0.1',2026).get_client_version().startswith('0.9.16'):raise RuntimeError('Run with the bundled Python, not the lab Python 3.10')
    cfg['carla_root']=str(root);local=ROOT/'lab.local.json'
    if local.exists():shutil.copy2(local,local.with_name('lab.local.'+uuid.uuid4().hex+'.backup'))
    local.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
    subprocess.run([sys.executable,'lab_preflight.py'],cwd=ROOT,check=True)
    print('Portable environment ready. Run 52_LAB_START.bat; on-site three-display verification remains.')

if __name__=='__main__':main()
