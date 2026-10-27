"""Small, cached geographic context. Never infer building semantics from RGB."""
import json
import math
import re
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parent
ATTRIBUTION='© OpenStreetMap contributors'
LICENSE_URL='https://www.openstreetmap.org/copyright'


def georeference_origin(text):
    def value(name):
        match=re.search(r'\+(?:=)?'+name+r'=([-+\d.eE]+)',text or '')
        if match is None:raise ValueError('Missing geographic origin '+name)
        return float(match[1])
    return value('lat_0'),value('lon_0'),value('alt_0')


def ecef(latitude,longitude,altitude=0.):
    lat,lon=np.radians([latitude,longitude]);a=6378137.;e2=6.6943799901413165e-3
    n=a/math.sqrt(1.-e2*math.sin(lat)**2)
    return np.array([(n+altitude)*math.cos(lat)*math.cos(lon),
        (n+altitude)*math.cos(lat)*math.sin(lon),(n*(1.-e2)+altitude)*math.sin(lat)])


def enu_basis(origin):
    lat,lon=np.radians(origin[:2]);sl,cl=math.sin(lat),math.cos(lat);so,co=math.sin(lon),math.cos(lon)
    return np.array([[-so,co,0.],[-sl*co,-sl*so,cl],[cl*co,cl*so,sl]])


def geographic_to_carla(latitude,longitude,origin):
    east,north,_=enu_basis(origin)@(ecef(latitude,longitude,origin[2])-ecef(*origin))
    return [float(east),float(-north)]


def carla_to_geographic(x,y,origin):
    point=ecef(*origin)+enu_basis(origin).T@np.array([x,-y,0.])
    px,py,pz=point;p=math.hypot(px,py);e2=6.6943799901413165e-3
    lat=math.atan2(pz,p*(1.-e2))
    for _ in range(8):
        n=6378137./math.sqrt(1.-e2*math.sin(lat)**2)
        lat=math.atan2(pz+e2*n*math.sin(lat),p)
    return float(math.degrees(lat)),float(math.degrees(math.atan2(py,px)))


def load_context(scene):
    scene_id=getattr(scene,'scene_id',None)
    if not scene_id:return dict(buildings=[],context_roads=[],context_source=None)
    path=ROOT.parent/'cache/map-context'/(scene_id+'.json')
    if not path.is_file():return dict(buildings=[],context_roads=[],context_source=None)
    value=json.loads(path.read_text(encoding='utf-8'))
    if value.get('scene_id')!=scene.scene_id or value.get('coordinate_frame')!='carla_xy':
        raise ValueError('Map context/source frame mismatch')
    return dict(buildings=value['buildings'],context_roads=value['roads'],
        context_source=dict(name='OpenStreetMap',attribution=ATTRIBUTION,license_url=LICENSE_URL,
            building_count=len(value['buildings']),road_count=len(value['roads'])))
