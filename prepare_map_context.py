"""Fetch nearby OSM footprints once; coordinates and cache remain outside Git."""
import argparse
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from map_context import georeference_origin,geographic_to_carla,carla_to_geographic,ATTRIBUTION,LICENSE_URL
from scene_bridge import Scene

ROOT=Path(__file__).resolve().parent


def assemble_rings(segments):
    pending=[list(s) for s in segments if len(s)>=2];rings=[]
    while pending:
        ring=pending.pop()
        while ring[0]!=ring[-1]:
            for i,part in enumerate(pending):
                if ring[-1]==part[0]:ring.extend(part[1:]);pending.pop(i);break
                if ring[-1]==part[-1]:ring.extend(part[-2::-1]);pending.pop(i);break
                if ring[0]==part[-1]:ring=part[:-1]+ring;pending.pop(i);break
                if ring[0]==part[0]:ring=part[:0:-1]+ring;pending.pop(i);break
            else:break
        if ring[0]==ring[-1] and len(ring)>=4:rings.append(ring)
    return rings


def osm_map_elements(data):
    tree=ET.fromstring(data)
    nodes={int(n.get('id')):dict(lat=float(n.get('lat')),lon=float(n.get('lon'))) for n in tree.findall('node')}
    ways={}
    for way in tree.findall('way'):
        refs=[int(n.get('ref')) for n in way.findall('nd')]
        if any(ref not in nodes for ref in refs):continue
        identifier=int(way.get('id'));ways[identifier]=dict(type='way',id=identifier,
            tags={t.get('k'):t.get('v') for t in way.findall('tag')},geometry=[nodes[ref] for ref in refs])
    elements=list(ways.values())
    for relation in tree.findall('relation'):
        members=[dict(type='way',ref=int(m.get('ref')),role=m.get('role'),geometry=ways[int(m.get('ref'))]['geometry'])
            for m in relation.findall('member') if m.get('type')=='way' and int(m.get('ref')) in ways]
        elements.append(dict(type='relation',id=int(relation.get('id')),tags={t.get('k'):t.get('v') for t in relation.findall('tag')},members=members))
    return dict(elements=elements)


def prepare(profile,endpoint='https://overpass.private.coffee/api/interpreter',provider='overpass'):
    scene=Scene(profile);origin=georeference_origin(ET.fromstring(scene.road).findtext('header/geoReference'))
    route=scene.route[:,:2,3].copy();route[:,1]*=-1
    low=route.min(0)-220.;high=route.max(0)+220.
    corners=[carla_to_geographic(x,y,origin) for x in [low[0],high[0]] for y in [low[1],high[1]]]
    south,west=np.min(corners,axis=0);north,east=np.max(corners,axis=0)
    bbox=','.join(f'{x:.7f}' for x in (south,west,north,east))
    folder=ROOT.parent/'cache/map-context';folder.mkdir(parents=True,exist_ok=True)
    raw_path=folder/(scene.scene_id+'-osm.json')
    if raw_path.exists():raw=json.loads(raw_path.read_text(encoding='utf-8'))
    else:
        query=f'[out:json][timeout:35];(way["building"]({bbox});relation["building"]["type"="multipolygon"]({bbox});way["highway"~"^(motorway|motorway_link|trunk|primary|secondary|tertiary|residential|service|unclassified)$"]({bbox}););out geom;'
        if provider=='osm-map':
            # Three small, one-off extracts; never request this during driving.
            api_bbox=','.join(f'{x:.7f}' for x in (west,south,east,north))
            request=urllib.request.Request('https://api.openstreetmap.org/api/0.6/map?bbox='+api_bbox,
                headers={'User-Agent':'Hongik-Research-HMI/1.0'})
            with urllib.request.urlopen(request,timeout=40) as response:data=response.read()
            (folder/(scene.scene_id+'-osm-map.xml')).write_bytes(data);raw=osm_map_elements(data)
        else:
            request=urllib.request.Request(endpoint,
                data=urllib.parse.urlencode({'data':query}).encode(),headers={'User-Agent':'Hongik-Research-HMI/1.0'})
            with urllib.request.urlopen(request,timeout=50) as response:raw=json.load(response)
        raw_path.write_text(json.dumps(raw,ensure_ascii=False),encoding='utf-8')
    def points(geometry):return [geographic_to_carla(p['lat'],p['lon'],origin) for p in geometry]
    def close_to_route(polygon):
        p=np.asarray(polygon);return bool(np.min(np.linalg.norm(p[:,None,:]-route[None,:,:],axis=-1))<220.)
    buildings=[];roads=[];relation_ways=set()
    for element in raw['elements']:
        if element['type']=='relation' and element.get('tags',{}).get('building'):
            relation_ways.update(m['ref'] for m in element.get('members',[]) if m['type']=='way')
    for element in raw['elements']:
        tags=element.get('tags',{});identifier=element['type']+'/'+str(element['id'])
        if tags.get('building') and tags['building']!='no':
            if element['type']=='way' and element['id'] in relation_ways:continue
            segments=[[(p['lat'],p['lon']) for p in element.get('geometry',[])]] if element['type']=='way' else [
                [(p['lat'],p['lon']) for p in m.get('geometry',[])] for m in element.get('members',[]) if m.get('role')=='outer']
            for i,ring in enumerate(assemble_rings(segments)):
                polygon=[geographic_to_carla(lat,lon,origin) for lat,lon in ring]
                if close_to_route(polygon):buildings.append(dict(id=identifier+'/'+str(i),points=polygon,name=tags.get('name','')))
        elif tags.get('highway') and element['type']=='way':
            line=points(element.get('geometry',[]))
            if len(line)<2 or not close_to_route(line):continue
            try:lanes=float(tags.get('lanes',2))
            except ValueError:lanes=2.
            roads.append(dict(id=identifier,points=line,width=max(3.,min(24.,lanes*3.5)),kind=tags['highway']))
    result=dict(scene_id=scene.scene_id,coordinate_frame='carla_xy',profile=profile,
        source='OpenStreetMap',attribution=ATTRIBUTION,license_url=LICENSE_URL,retrieved_at=time.strftime('%Y-%m-%d'),buildings=buildings,roads=roads)
    output=folder/(scene.scene_id+'.json')
    if output.exists():raise RuntimeError('Preserve the existing context cache before replacing it')
    output.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps(dict(profile=profile,buildings=len(buildings),roads=len(roads),cache=str(output)),ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--profile',choices=['night','fog','congestion'],required=True)
    parser.add_argument('--endpoint',default='https://overpass.private.coffee/api/interpreter')
    parser.add_argument('--provider',choices=['overpass','osm-map'],default='overpass')
    args=parser.parse_args();prepare(args.profile,args.endpoint,args.provider)
