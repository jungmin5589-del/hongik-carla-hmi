"""Map geometry and departure checks use CARLA coordinates, never OSM guesses."""
import math
import numpy as np


def route_atlas(route,map_name):
    """Include actual adjacent driving/parking/shoulder lanes at route waypoints."""
    groups={}
    for anchor in route.waypoints:
        neighbors=[anchor];seen={anchor.id}
        for side in ('left','right'):
            cursor=anchor
            for _ in range(12):
                direction=side if cursor.lane_id*anchor.lane_id>0 else ('right' if side=='left' else 'left')
                cursor=getattr(cursor,'get_'+direction+'_lane')()
                if cursor is None or cursor.id in seen:break
                seen.add(cursor.id);neighbors.append(cursor)
        for wp in neighbors:
            kind=str(wp.lane_type)
            if kind not in ('Driving','Parking','Shoulder') or wp.lane_width<.1:continue
            key=(wp.road_id,wp.section_id,wp.lane_id,kind)
            p=wp.transform.location
            groups.setdefault(key,{})[round(wp.s,3)]=(float(wp.s),float(p.x),float(p.y),float(wp.lane_width))
    roads=[]
    for key,samples in groups.items():
        rows=sorted(samples.values());part=[]
        def flush():
            if len(part)>1:
                roads.append(dict(points=[[r[1],r[2]] for r in part],width=min(r[3] for r in part),kind=key[3],road_id=key[0],lane_id=key[2]))
        for row in rows:
            if part and math.hypot(row[1]-part[-1][1],row[2]-part[-1][2])>12:
                flush();part=[]
            part.append(row)
        flush()
    return dict(map=map_name,coordinate_frame='carla_xy',roads=roads,destinations=[],buildings=[],context_source=None)


def start_alignment(route,vehicles,snapshot=None):
    """Check actual settled actors against their assigned path before departure."""
    rows=[]
    for item in vehicles:
        state=snapshot.find(item['actor'].id) if snapshot else item['actor']
        tr=state.get_transform();point,yaw=route.sample(item['s'],item['offset'])
        distance=math.hypot(tr.location.x-point[0],tr.location.y-point[1])
        heading=abs((tr.rotation.yaw-math.degrees(yaw)+180)%360-180)
        speed=state.get_velocity().length()*3.6
        valid=distance<=.75 and heading<=10. and speed<.6
        rows.append(dict(id=item['actor'].id,role=item['role'],position_error_m=round(distance,3),heading_error_deg=round(heading,2),speed_kph=round(speed,2),valid=valid))
    return dict(ready=bool(rows) and all(r['valid'] for r in rows),vehicles=rows)


def route_index(route,distance,stride=3):
    at=min(route.length,max(0.,distance)) if hasattr(route,'cross_s') else float(distance%route.length)
    return int(np.searchsorted(route.arc[::stride],at,side='right')-1)


def steering_geometry(actor):
    physics=actor.get_physics_control();tr=actor.get_transform()
    front=[w for w in physics.wheels if w.max_steer_angle>1.]
    rear=[w for w in physics.wheels if w.max_steer_angle<=1.]
    if not front or not rear:raise ValueError('Vehicle steering axles unavailable')
    f=np.mean([[w.position.x,w.position.y] for w in front],axis=0)/100.
    r=np.mean([[w.position.x,w.position.y] for w in rear],axis=0)/100.
    yaw=math.radians(tr.rotation.yaw);forward=np.array([math.cos(yaw),math.sin(yaw)])
    wheelbase=float(abs((f-r)@forward));rear_offset=float((r-[tr.location.x,tr.location.y])@forward)
    maximum=math.radians(float(np.mean([w.max_steer_angle for w in front])))
    if not 1.<wheelbase<12. or not .1<maximum<1.55:raise ValueError('Invalid vehicle steering geometry')
    return dict(wheelbase=wheelbase,rear_offset=rear_offset,max_steer=maximum,
                steering_curve=[(float(p.x),float(p.y)) for p in getattr(physics,'steering_curve',[])])


def tracking_alignment(route,item,transform=None):
    tr=transform or item['actor'].get_transform();point,yaw=route.sample(item['s'],item['offset'])
    return dict(id=item['actor'].id,role=item['role'],target_offset_m=round(item['offset'],3),
                position_error_m=round(math.hypot(tr.location.x-point[0],tr.location.y-point[1]),3),
                heading_error_deg=round(abs((tr.rotation.yaw-math.degrees(yaw)+180)%360-180),2),
                target_kph=round(item.get('speed',0.),2))


def ego_lane(lanes):
    driving=[lane for lane in lanes if lane.get('kind','Driving')=='Driving' and lane.get('points')]
    if not driving:return 1,0
    def distance(lane):
        point=min(lane['points'],key=lambda p:abs(p['forward_m']))
        return abs(point['right_m'])
    return 1+min(range(len(driving)),key=lambda i:distance(driving[i])),len(driving)


def cached_map(bridge):
    value=getattr(bridge,'road_map',None)
    if value is None:
        value=bridge.world.get_map();bridge.road_map=value
    return value
