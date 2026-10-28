"""Version public configuration and dependency pins, never runtime secrets/data."""
import importlib.metadata,json,platform
from pathlib import Path
from performance_presets import PRESETS
from fog_scene import LEAD_TRACK_ID,LEAD_ASSET_NAME,CONTEXT_TRACK_IDS,ONSET_SECONDS,BASE_GAP_M,FOG_BUILDUP_SECONDS,EXTINCTION_TIMES,EXTINCTION_BETAS
from night_weaving import BoundaryWeaving
ROOT=Path(__file__).resolve().parent

def snapshot():
    packages={}
    for name in ['carla','numpy','scipy','Pillow','pygame','grpcio','requests','cryptography']:
        try:packages[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:pass
    result=dict(schema_version=1,python=platform.python_version(),platform=platform.system(),
        carla=dict(version='0.9.16',graphics='DX12',asynchronous=True,physics_only=True,rpc_port=2016),
        nurec=dict(release='26.4',renderer='trained',cache_size=1,grpc_port=46435,
            image='nvcr.io/nvidia/nre/nre-ga@sha256:97f43e7130c5636ce3e80ea3184d97f56a87fdd989b05cce42230881dbdea284',wsl='Ubuntu-22.04'),
        application=dict(drive_port=8774,chooser_port=8775,mobile_http_port=8776,mobile_https_port=8777,
            default_performance='standard',fps_cap=30,fps_cap_is_not_measured_performance=True,scenario_load='essential',static_view_cache_enabled=False),
        performance_presets=PRESETS,packages=packages,
        memory=dict(startup_commit_floor_gib=16,validation_commit_floor_gib=2),
        external_resources=dict(models='separately licensed; not in Git',narration='local cached Qwen Sohee; not in Git',private_keys='local only; never in Git'))
    folder=ROOT/'settings';folder.mkdir(exist_ok=True)
    (folder/'runtime-lock.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (folder/'requirements.lock.txt').write_text('\n'.join(f'{k}=={v}' for k,v in packages.items())+'\n',encoding='utf-8')
    scenarios=dict(congestion=dict(lanes=4,ego_lane=2,lead_speed_range_kph=[25,35],large_vehicles=3,
        fast_speed_kph=90,fast_spacing_m=20,standard_fast_count=12,compact_fast_count=8),
        night=dict(ego_straight=True,native_lead='108',base_gap_m=BoundaryWeaving.BASE_GAP,widen_gap_m=BoundaryWeaving.WIDE_GAP,weaving_boundary_m=-1.8,weaving_amplitude_m=.65),
        fog=dict(duration_s=300,onset_s=ONSET_SECONDS,buildup_s=FOG_BUILDUP_SECONDS,base_gap_m=BASE_GAP_M,lead=LEAD_TRACK_ID,native_context=list(CONTEXT_TRACK_IDS),
            lead_asset=LEAD_ASSET_NAME,appearance='fixed source-time asset; no retraining',source_time='continuous route projection',
            extinction_keys_s=list(EXTINCTION_TIMES),extinction_beta=list(EXTINCTION_BETAS),
            compositor='same-frame native distance/opacity; camera-relative ground completion',physical_weather_engine=False))
    (folder/'scenarios.json').write_text(json.dumps(scenarios,indent=2),encoding='utf-8')
    return result

if __name__=='__main__':snapshot();print('Sanitized settings and dependency snapshot saved')
