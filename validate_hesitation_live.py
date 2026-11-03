"""Real CARLA waiting motion and stopped-vehicle checks; temporary close-up camera."""
import json,math,time,uuid,queue
from pathlib import Path
import carla
from validate_city_cases import get,post
from launch_live import memory_state

ROOT=Path(__file__).resolve().parent

def main():
    folder=ROOT/'validation'/('hesitation-'+uuid.uuid4().hex[:10]);folder.mkdir();print(str(folder),flush=True)
    post('/api/select',{'profile':'yield'});deadline=time.monotonic()+120
    while time.monotonic()<deadline:
        state=json.loads(get('/state'))
        if state.get('error'):raise RuntimeError(state['error'])
        if state['phase']=='live' and state.get('profile')=='yield':break
        time.sleep(.2)
    else:raise RuntimeError('Yield profile not ready')
    post('/control',{'mode':'auto'});deadline=time.monotonic()+75;camera=None;waiting=None;rows=[];images=queue.Queue(maxsize=2);captures=[.5,2.,3.5,5.5,8.5,11.5]
    client=carla.Client('127.0.0.1',2026);client.set_timeout(8);world=client.get_world()
    def image_ready(img):
        if images.full():
            try:images.get_nowait()
            except queue.Empty:pass
        try:images.put_nowait(img)
        except queue.Full:pass
    try:
        while time.monotonic()<deadline:
            if memory_state()<2:raise RuntimeError('Validation commit guard: below 2 GiB')
            state=json.loads(get('/state'));sc=state['scenario'];phase=sc['yielding']['phase']
            if state.get('error'):raise RuntimeError(state['error'])
            if phase=='mutual_wait':
                if waiting is None:
                    waiting=time.monotonic();ego=next(a for a in world.get_actors().filter('vehicle.*') if a.attributes.get('role_name')=='hongik_native_ego');ped=next(a for a in world.get_actors().filter('walker.*') if a.attributes.get('role_name')=='hongik_native_pedestrian')
                    eye=ego.get_transform().location+ego.get_transform().get_forward_vector()*1.5+carla.Location(z=1.35)
                    point=ped.get_location();yaw=math.degrees(math.atan2(point.y-eye.y,point.x-eye.x))
                    bp=world.get_blueprint_library().find('sensor.camera.rgb')
                    for key,value in {'image_size_x':640,'image_size_y':640,'fov':35,'sensor_tick':1/15,'motion_blur_intensity':0.}.items():bp.set_attribute(key,str(value))
                    camera=world.spawn_actor(bp,carla.Transform(eye,carla.Rotation(pitch=-4,yaw=yaw)));camera.listen(image_ready)
                age=time.monotonic()-waiting;rows.append(state)
                if state['speed_kph']>.6:raise RuntimeError('Vehicle moved during pedestrian hesitation')
                if sc.get('collision_count',0):raise RuntimeError('Unexpected collision')
                if captures and age>=captures[0]:
                    target=captures.pop(0);(folder/(str(target)+'-drive.jpg')).write_bytes(get('/frame.jpg'))
                    image=images.get(timeout=3);image.save_to_disk(str(folder/(str(target)+'-pedestrian.png')))
                    print('captured',target,sc['yielding']['hesitation'],flush=True)
                if age>=13:break
            time.sleep(.08)
        if not rows or captures:raise RuntimeError('Waiting phase did not produce all captures')
        offsets=[s['scenario']['yielding']['hesitation']['actual_offset_m'] for s in rows]
        assert max(offsets)-min(offsets)>.3
        assert all(s['scenario']['yielding']['hesitation']['gait']=='matching_native_cycle' for s in rows)
        (folder/'states.json').write_text(json.dumps(rows),encoding='utf-8')
        result=dict(actual_carla=True,vehicle_stopped=True,no_collision=True,waiting_duration_s=time.monotonic()-waiting,
            half_step_range_m=max(offsets)-min(offsets),native_matching_model_gait=True,temporary_observer_camera=True)
        (folder/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
    finally:
        post('/control',{'mode':'paused'})
        if camera:camera.stop();camera.destroy()

if __name__=='__main__':main()
