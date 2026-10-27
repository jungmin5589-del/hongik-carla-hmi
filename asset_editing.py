"""Use the installed 26.4 renderer's asset-editing protocol in an isolated pool.

The course CARLA client's older generated modules remain unchanged. Runtime
descriptors were copied from the pinned official image, not downloaded code run.
"""
import ast
from pathlib import Path
from google.protobuf import descriptor_pool, message_factory

ROOT=Path(__file__).resolve().parents[1]
POOL=descriptor_pool.DescriptorPool()
for name in ('common','sensorsim'):
    tree=ast.parse((ROOT/'source/runtime-protocol-26.4'/(name+'_pb2.py')).read_text(encoding='utf-8'))
    call=next(n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='AddSerializedFile')
    POOL.AddSerializedFile(ast.literal_eval(call.args[0]))

def message(name):
    for prefix in ('nre.grpc.protos.sensorsim.','nre.grpc.protos.common.'):
        try:return message_factory.GetMessageClass(POOL.FindMessageTypeByName(prefix+name))
        except KeyError:pass
    raise KeyError(name)

def rpc(channel,name,request,response):
    return channel.unary_unary('/nre.grpc.protos.sensorsim.SensorsimService/'+name,
        request_serializer=lambda value:value.SerializeToString(),response_deserializer=message(response).FromString)(request,timeout=90)

def ensure_asset_tracks(channel,scene_id,start_us,end_us,specs):
    if not specs:return
    current=rpc(channel,'get_dynamic_objects',message('AvailableDynamicObjectsRequest')(scene_id=scene_id),'AvailableDynamicObjectsReturn')
    ids={r.id for r in current.dynamic_objects};wanted={s['id'] for s in specs}
    if wanted<=ids:return
    if wanted&ids:
        rpc(channel,'restore_model_parameters',message('RestoreModelParametersRequest')(scene_id=scene_id),'Empty')
    request=message('EditAssetsRequest')(scene_id=scene_id)
    for spec in specs:
        track=request.insert.add(id=spec['id'],semantic_class=spec['semantic_class'],asset_id=spec['asset_id'])
        track.object_size.CopyFrom(message('AABB')(size_x=spec['size'][0],size_y=spec['size'][1],size_z=spec['size'][2]))
        for stamp in (start_us,end_us):
            pose=track.trajectory.poses.add(timestamp_us=stamp).pose
            pose.vec.z=-1000;pose.quat.w=1
    result=rpc(channel,'edit_assets',request,'EditAssetsResponse')
    if not result.success:raise RuntimeError('Native traffic insertion failed: '+result.message)

if __name__=='__main__':
    for service in POOL.FindFileByName('nre/grpc/protos/sensorsim.proto').services_by_name.values():
        for m in service.methods:
            if 'asset' in m.name or 'model' in m.name:
                print(m.name,m.input_type.name,m.output_type.name)
                for kind in (m.input_type,m.output_type):
                    print(kind.name,[(f.name,f.message_type.full_name if f.message_type else f.type) for f in kind.fields])
    for name in ('DynamicObjectTrack','Trajectory','TimestampedPose','AABB'):
        try:print(name,[(f.name,f.message_type.full_name if f.message_type else f.type) for f in message(name).DESCRIPTOR.fields])
        except KeyError:pass
