"""Private, local CARLA 0.9.16 -> NuRec 26.4 live camera bridge.

Data stays on the user's local machine. No prerecorded frames are served.
Projection formula is from NVIDIA's MIT CARLA integration (projection_functions.py).
"""
import argparse
import hashlib
import io
import json
import math
import sys
import threading
import time
import traceback
import zipfile
import xml.etree.ElementTree as ET
from scipy.ndimage import gaussian_filter1d
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent
TRIAL = ROOT.parent
OFFICIAL = Path(r"D:\CARLA-Build\carla-0.9.16\PythonAPI\examples\nvidia\nurec")
sys.path.insert(0, str(OFFICIAL))
sys.path.insert(0, str(ROOT / "vendor"))
import carla
import grpc
import numpy as np
from PIL import Image
from scipy.spatial.transform import Rotation, Slerp
from projection_functions import get_t_rig_enu_from_ecef
from nre.grpc.protos import common_pb2 as common
from nre.grpc.protos import sensorsim_pb2 as proto
from nre.grpc.protos.sensorsim_pb2_grpc import SensorsimServiceStub
from scenario2 import Scenario2
from night_overtake import NightOvertakeScenario
from night_weaving import BoundaryWeaving, recorded_track_height
from congestion import Congestion
from fog_trial import DenseFog
from fog_effect import FogEffect
from navigation_adapter import NavigationAdapter, navigation_html, static_asset
from voice_bank import audio_path as narration_audio_path
from profile_sources import manifest_name
from highway_blockade import HighwayBlockade
from asset_editing import ensure_asset_tracks
from high_beam import HighBeamEffect
from rendering_mode import enable_physics_only, renderer_matches
from scenario_workload import required_proxy_ids
from actor_visibility import visible_fast_traffic
from frame_validation import validate_jpeg
from range_transport import decode_range_hint
from performance_presets import traffic_config
from fog_scene import LEAD_TRACK_ID as FOG_LEAD_TRACK_ID

MIRROR = np.diag([1., -1., 1., 1.])
QUALITY_PRESETS = {"smooth": (640, 360), "balanced": (960, 540), "high": (1280, 720), "fullhd": (1920, 1080)}


def grpc_pose(matrix):
    q = Rotation.from_matrix(matrix[:3, :3]).as_quat()
    t = matrix[:3, 3]
    return common.Pose(vec=common.Vec3(x=t[0], y=t[1], z=t[2]),
                       quat=common.Quat(x=q[0], y=q[1], z=q[2], w=q[3]))


def carla_matrix(matrix):
    return MIRROR @ matrix @ MIRROR


def to_transform(matrix):
    left = carla_matrix(matrix)
    yaw = math.degrees(math.atan2(left[1, 0], left[0, 0]))
    pitch = math.degrees(math.atan2(left[2, 0], math.hypot(left[0, 0], left[1, 0])))
    roll = math.degrees(math.atan2(-left[2, 1], left[2, 2]))
    return carla.Transform(carla.Location(*left[:3, 3].tolist()),
                           carla.Rotation(pitch=pitch, yaw=yaw, roll=roll))


class Scene:
    def __init__(self, profile='night'):
        self.profile = profile
        manifest = manifest_name(profile)
        report = json.loads((TRIAL / 'reports' / manifest).read_text())
        if report["phase"] != "download_verified":
            raise RuntimeError("Verified authorized scene required")
        stored_path = report["local_path"]
        if stored_path.startswith("/mnt/d/"):
            stored_path = "D:/" + stored_path[len("/mnt/d/"):]
        self.path = Path(stored_path)
        if self.path.stat().st_size != report["actual_bytes"]:
            raise RuntimeError("Scene file size changed")
        with zipfile.ZipFile(self.path) as z:
            self.road = z.read("map.xodr").decode()
            rig = json.loads(z.read("rig_trajectories.json"))
            self.info = json.loads(z.read("data_info.json"))
            self.tracks = json.loads(z.read("sequence_tracks.json"))["dummy_chunk_id"]
        self.alignment = get_t_rig_enu_from_ecef(np.array(rig["T_world_base"]), self.road)
        self.inverse_alignment = np.linalg.inv(self.alignment)
        traj = rig["rig_trajectories"][0]
        self.poses = np.array(traj["T_rig_worlds"])
        self.timestamps = np.array(traj["T_rig_world_timestamps_us"])
        self.route = self.alignment @ self.poses
        if profile == 'congestion':
            # The source camera drove lane 3; move the independent ego to lane 2.
            # Preserve source road height and heading, with a gentle constant lateral shift.
            self.route=self.route.copy()
            self.route[:,:3,3]+=self.route[:,:3,1]*3.6
        self.camera_id = "camera_front_wide_120fov"
        calibration = next(c for c in rig["camera_calibrations"].values()
                           if c["logical_sensor_name"] == self.camera_id)
        self.camera_mount = np.array(calibration["T_sensor_rig"])
        self.scene_id = self.info["sequence_id"]
        self.start_us = self.info["pose-range"]["start-timestamp_us"]
        self.end_us = self.info["pose-range"]["end-timestamp_us"]

    def raw_corridor_road(self):
        """Retain source geometry near the recorded route, pruning dangling links."""
        full_map = carla.Map("nurec_source", self.road)
        selected = {str(full_map.get_waypoint(to_transform(p).location).road_id) for p in self.route}
        tree = ET.fromstring(self.road)
        roads = tree.findall("road")
        # Keep adjacent connection roads belonging to the route's junctions.
        junction_ids = {r.get("junction") for r in roads if r.get("id") in selected} - {"-1"}
        for r in roads:
            if r.get("junction") in junction_ids:
                selected.add(r.get("id"))
        for r in roads:
            if r.get("id") not in selected:
                tree.remove(r)
        junctions = {j.get("id"): j for j in tree.findall("junction")}
        for j in list(junctions.values()):
            for conn in list(j.findall("connection")):
                if conn.get("incomingRoad") not in selected or conn.get("connectingRoad") not in selected:
                    j.remove(conn)
            if not j.findall("connection"):
                tree.remove(j)
                del junctions[j.get("id")]
        for r in tree.findall("road"):
            if r.get("junction") not in junctions:
                r.set("junction", "-1")
            link = r.find("link")
            if link is not None:
                for element in list(link):
                    valid_ids = selected if element.get("elementType") == "road" else junctions
                    if element.get("elementId") not in valid_ids:
                        link.remove(element)
        return ET.tostring(tree, encoding="unicode"), len(selected)

    def corridor_road(self):
        """Continuous collision surface derived from the measured rig trajectory.

        The original 26.04 OpenDRIVE has mesh holes/steps under CARLA 0.9.16.
        NuRec still renders the unchanged source scene. This narrow physics layer
        preserves measured world coordinates, curvature and height along the drive.
        It is not a claim that the full source lane topology was imported intact.
        """
        centre = gaussian_filter1d(self.route[:, :3, 3], sigma=1.2, axis=0, mode="nearest")
        keep = [0]
        for i in range(1, len(centre)):
            if np.linalg.norm(centre[i, :2] - centre[keep[-1], :2]) >= .75:
                keep.append(i)
        centre = centre[keep]
        tangent = np.gradient(centre, axis=0)
        tangent /= np.linalg.norm(tangent[:, :2], axis=1)[:, None]
        left = np.column_stack((-tangent[:, 1], tangent[:, 0], np.zeros(len(tangent))))
        # Right driving lane -1 is centred on the recorded vehicle trajectory.
        reference = centre + left * 1.8
        reference = np.vstack((reference[0] - tangent[0] * 12, reference,
                               reference[-1] + tangent[-1] * 12))
        lengths = np.linalg.norm(np.diff(reference[:, :2], axis=0), axis=1)
        starts = np.r_[0., np.cumsum(lengths)]
        tree = ET.Element("OpenDRIVE")
        header = ET.SubElement(tree, "header", revMajor="1", revMinor="4", name="NuRec recorded drive collision layer",
                              version="1.0", vendor="Local private NuRec CARLA integration")
        original_geo = ET.fromstring(self.road).find("header/geoReference")
        if original_geo is not None:
            ET.SubElement(header, "geoReference").text = original_geo.text
        road = ET.SubElement(tree, "road", name="Measured trajectory corridor", length=str(starts[-1]), id="99001", junction="-1")
        if self.profile in ('congestion','fog'):
            road.set('id', '99002')
        if self.profile=='congestion':road.set('id','99003')
        plan = ET.SubElement(road, "planView")
        elevation = ET.SubElement(road, "elevationProfile")
        for i, length in enumerate(lengths):
            delta = reference[i + 1] - reference[i]
            geometry = ET.SubElement(plan, "geometry", s=str(starts[i]), x=str(reference[i, 0]),
                y=str(reference[i, 1]), hdg=str(math.atan2(delta[1], delta[0])), length=str(length))
            ET.SubElement(geometry, "line")
            ET.SubElement(elevation, "elevation", s=str(starts[i]), a=str(reference[i, 2]),
                          b=str(delta[2] / length), c="0", d="0")
        lanes = ET.SubElement(road, "lanes")
        section = ET.SubElement(lanes, "laneSection", s="0")
        middle = ET.SubElement(section, "center")
        ET.SubElement(middle, "lane", id="0", type="none", level="false")
        for side, sign in (("left", 1), ("right", -1)):
            group = ET.SubElement(section, side)
            indices=(1,) if self.profile=='congestion' and side=='left' else (1,2,3) if self.profile=='congestion' else (1,2)
            for i in indices:
                lane = ET.SubElement(group, "lane", id=str(i * sign), type="driving", level="false")
                ET.SubElement(lane, "width", sOffset="0", a="3.6", b="0", c="0", d="0")
                ET.SubElement(lane, "roadMark", sOffset="0", type="broken", weight="standard",
                              color="white", width="0.12", laneChange="both")
        return ET.tostring(tree, encoding="unicode"), 1

    def nearest(self, transform):
        xy = np.array([transform.location.x, -transform.location.y])
        distances = np.linalg.norm(self.route[:, :2, 3] - xy, axis=1)
        i = int(distances.argmin())
        # Steering keeps the nearest-sample index; lateral error is continuous.
        points = self.route[:, :2, 3]
        if len(points) < 2:
            return i, float(distances[i])
        segments = points[1:] - points[:-1]
        lengths2 = np.einsum('ij,ij->i', segments, segments)
        fraction = np.clip(np.einsum('ij,ij->i', xy-points[:-1], segments) /
                           np.maximum(lengths2, 1e-12), 0., 1.)
        projected = points[:-1] + fraction[:, None] * segments
        return i, float(np.linalg.norm(projected-xy, axis=1).min())

    def source_timestamp(self, transform):
        """Advance reconstructed traffic continuously along the measured route.

        A nearest-pose timestamp holds traffic still between recorded points,
        then jumps an entire source sample. This is especially visible when the
        independent CARLA ego drives more slowly than the recording vehicle.
        Pausing the ego also freezes source time; no wall-clock playback is used.
        """
        xy = np.array([transform.location.x, -transform.location.y])
        points = self.route[:, :2, 3]
        if len(points) < 2:
            stamp = self.timestamps[0]
        else:
            segments = np.diff(points, axis=0)
            lengths2 = np.einsum('ij,ij->i', segments, segments)
            fraction = np.clip(np.einsum('ij,ij->i', xy-points[:-1], segments) /
                               np.maximum(lengths2, 1e-12), 0., 1.)
            squared_distance = np.sum((points[:-1]+fraction[:,None]*segments-xy)**2, axis=1)
            # Ignore stationary/duplicate segments if any real segment exists.
            # Otherwise a duplicate at a junction can pin time to an old sample.
            if np.any(lengths2 > 1e-12):
                squared_distance[lengths2 <= 1e-12] = np.inf
            k = int(np.argmin(squared_distance))
            stamp = self.timestamps[k] + fraction[k]*(self.timestamps[k+1]-self.timestamps[k])
        return int(np.clip(stamp, self.start_us, self.end_us-2))

    def camera_pose(self, transform):
        # CARLA actor API is left handed. NuRec expects the original right handed
        # scene frame, before the server's own world_to_nre conversion.
        ego = carla_matrix(np.array(transform.get_matrix()))
        return self.inverse_alignment @ ego @ self.camera_mount


class Bridge:
    def __init__(self, args):
        self.args = args
        self.scene = Scene(args.profile)
        self.client = carla.Client("127.0.0.1", args.carla_port)
        self.client.set_timeout(120)
        self.stop = threading.Event()
        self.render_wake = threading.Event()
        self.lock = threading.Lock()
        self.track_lock = threading.RLock()
        self.frame_event = threading.Condition()
        self.jpeg = None
        self.frame_id = 0
        self.last_frame_time = 0.
        self.rgb_audit_time = 0.
        self.validated_image_size = None
        self.render_size = (args.width, args.height)
        self.quality = next((key for key, size in QUALITY_PRESETS.items() if size == self.render_size), "custom")
        self.state = {"phase": "loading_road", "speed_kph": 0, "mode": "paused",
                      "frames": 0, "source": "CARLA pose -> NuRec gRPC", "error": None,
                      "quality": self.quality, "width": args.width, "height": args.height,
                      "profile": args.profile, "scene_id": self.scene.scene_id}
        self.state['renderer_backend'] = getattr(args, 'renderer_backend', 'trained')
        self.state['target_fps'] = args.fps
        self.state['proxy_update_mode'] = getattr(args, 'proxy_update_mode', 'batch')
        self.state['scenario_load'] = getattr(args, 'scenario_load', 'full')
        self.state['traffic_load'] = getattr(args,'traffic_load','standard')
        if args.profile == 'night':
            self.state['night_mode'] = getattr(args, 'night_mode', 'straight')
        self.command = {"mode": "paused", "keys": {}, "last_input": 0., "reset": False}
        self.run_dir = ROOT / "runs" / time.strftime("%Y%m%d-%H%M%S")
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self.trace = (self.run_dir / "frames.jsonl").open("w", encoding="utf-8", buffering=1)
        if args.profile=='congestion':
            config=json.loads((TRIAL/'reports/wide-highway-v2-config.json').read_text(encoding='utf-8-sig'))
            config=traffic_config(config,getattr(args,'traffic_load','standard'))
            if config['scene_id']!=self.scene.scene_id:raise RuntimeError('Four-lane source/config mismatch')
            self.scenario=HighwayBlockade(self.scene.route,self.run_dir/'interactions.jsonl',config)
        elif args.profile=='fog':
            config = json.loads((TRIAL / 'reports/long-scene-config.json').read_text())
            if config['scene_id'] != self.scene.scene_id:
                raise RuntimeError('Long drive scene/config mismatch')
            trial=DenseFog if args.profile=='fog' else Congestion
            self.scenario = trial(self.scene.route, self.run_dir / 'interactions.jsonl', FOG_LEAD_TRACK_ID)
            from fog_scene import lead_asset_specs
            self.scenario.insert_asset_specs = lead_asset_specs()
        else:
            straight = getattr(args, 'night_mode', 'straight') == 'straight'
            trial = BoundaryWeaving if straight else NightOvertakeScenario
            self.scenario = trial(self.scene.route, self.run_dir / "interactions.jsonl")
            config_name = 'night-straight-v1-config.json' if straight else 'night-overtake-assets-v1-config.json'
            asset_config = json.loads((TRIAL / 'reports' / config_name).read_text(encoding='utf-8-sig'))
            if asset_config['scene_id'] != self.scene.scene_id:
                raise RuntimeError('Night crash asset/source mismatch')
            self.scenario.crash_asset_specs = asset_config['insert_assets']
        self.navigation = NavigationAdapter(self)
        self.fog_effect=FogEffect() if args.profile=='fog' else None
        self.high_beam_effect=HighBeamEffect() if args.profile=='congestion' else None
        self.last_light_state=None
        self.crash_held = False
        self.pre_contact_transform = None
        self.editable_ids = set()
        self.actors = []
        self.track_bbox_offsets = {}
        self.restore_no_rendering = None
        self.ready_for_driving=threading.Event()
        self.defer_initial_tracks=(getattr(args,'physics_only',False) and args.scenario_load=='essential'
            and isinstance(self.scenario,HighwayBlockade))
        self.setup_world()
        self.channel = grpc.insecure_channel("127.0.0.1:46435", options=[
            ("grpc.max_receive_message_length", 32 * 1024 * 1024),
            ("grpc.max_metadata_size", 128 * 1024),
            ("grpc.max_send_message_length", 32 * 1024 * 1024),
            ("grpc.initial_reconnect_backoff_ms", 200),
            ("grpc.max_reconnect_backoff_ms", 1000)])
        self.stub = SensorsimServiceStub(self.channel)

    def setup_world(self):
        if self.client.get_server_version() != self.client.get_client_version():
            raise RuntimeError("CARLA server/client version mismatch")
        corridor, road_count = self.scene.corridor_road()
        source_role = 'nurec_live_ego_' + hashlib.sha256((self.scene.scene_id+corridor).encode()).hexdigest()[:16]
        (self.run_dir / "corridor.xodr").write_text(corridor, encoding="utf-8")
        print(f"Loading source corridor: {road_count} roads", flush=True)
        current = self.client.get_world()
        ours = [a for a in current.get_actors() if a.attributes.get("role_name", "").startswith("nurec_")]
        old_ids = {r.get("id") for r in ET.fromstring(current.get_map().to_opendrive()).findall("road")}
        new_ids = {r.get("id") for r in ET.fromstring(corridor).findall("road")}
        if (ours and any(a.attributes.get('role_name')==source_role for a in ours)
                and old_ids == new_ids and current.get_map().name.endswith("OpenDriveMap")):
            for actor in ours:
                actor.destroy()
            self.world = current
            print("Reusing this trial's matched corridor", flush=True)
        else:
            self.world = self.client.generate_opendrive_world(corridor,
                carla.OpendriveGenerationParameters(vertex_distance=2., max_road_length=500.,
                    wall_height=0., additional_width=0.6, smooth_junctions=False,
                    enable_mesh_visibility=True))
        if self.world.get_settings().synchronous_mode:
            raise RuntimeError("Expected independent asynchronous CARLA test server")
        if getattr(self.args, 'physics_only', False):
            self.restore_no_rendering = enable_physics_only(self.world)
            self.state['carla_background_rendering'] = False
        self.map = self.world.get_map()
        bp = self.world.get_blueprint_library().find("vehicle.audi.a2")
        bp.set_attribute("role_name", source_role)
        tr = to_transform(self.scene.route[0])
        wp = self.map.get_waypoint(tr.location, project_to_road=True, lane_type=carla.LaneType.Driving)
        if wp is None or tr.location.distance(wp.transform.location) > 8:
            raise RuntimeError("NuRec and OpenDRIVE origin do not align within 8 m")
        self.initial_nearest = {"distance_m": tr.location.distance(wp.transform.location),
            "road_id": wp.road_id, "lane_id": wp.lane_id,
            "rig_z": tr.location.z, "road_z": wp.transform.location.z}
        # Keep the measured rig position in x/y; use generated road surface for physics.
        tr.rotation.pitch = 0
        tr.rotation.roll = 0
        tr.location.z = wp.transform.location.z + 1.0
        self.initial_transform = tr
        self.ego = self.world.try_spawn_actor(bp, tr)
        if self.ego is None:
            raise RuntimeError("Ego spawn obstructed at aligned road origin")
        self.actors.append(self.ego)
        self.ego.set_simulate_physics(True)
        self.ego.apply_control(carla.VehicleControl(brake=1., hand_brake=True))
        self.world.wait_for_tick(5)
        if self.defer_initial_tracks:
            self.track_actors=[];self.track_active={};self.track_failures=[]
            self.state.update(collision_proxy_count=0,collision_proxy_scope='initializing')
        else:
            self.setup_tracks()
        if getattr(self.scenario, 'OVERTAKE_TRIAL', False):
            sensor_bp=self.world.get_blueprint_library().find('sensor.other.collision')
            sensor=self.world.spawn_actor(sensor_bp,carla.Transform(),attach_to=self.ego)
            self.actors.append(sensor)
            sensor.listen(self.on_ego_collision)
        details = {"client_version": self.client.get_client_version(),
            "server_version": self.client.get_server_version(), "port": self.args.carla_port,
            "map": self.map.name, "synchronous_mode": self.world.get_settings().synchronous_mode,
            "ego_id": self.ego.id, "scene_id": self.scene.scene_id,
            "alignment": self.scene.alignment.tolist(), "initial_nearest": self.initial_nearest,
            "track_actors": len(self.track_actors), "resolution": [self.args.width, self.args.height],
            "collision_surface": "continuous surface derived from measured rig trajectory; not full original lane topology"}
        self.carla_ready_details=details
        ready_file='carla-warmup-ready.json' if self.defer_initial_tracks else 'carla-ready.json'
        (self.run_dir / ready_file).write_text(json.dumps(details, indent=2), encoding="utf-8")
        print(json.dumps(details), flush=True)
        self.state.update(phase="waiting_renderer", ego_id=self.ego.id)

    def setup_tracks(self, include_all=False):
        with self.track_lock:
            return self._setup_tracks(include_all)

    def _setup_tracks(self, include_all=False):
        if not hasattr(self,'track_actors'):
            self.track_actors = []
            self.track_active = {}
            self.track_failures = []
        required=required_proxy_ids(self.scenario,getattr(self.args,'scenario_load','full'),include_all)
        if required is not None:
            kept=[]
            for row in self.track_actors:
                track,actor,_,_=row
                if track in required:
                    kept.append(row)
                    continue
                actor.set_collisions(False)
                actor.destroy()
                self.actors=[a for a in self.actors if a.id!=actor.id]
                self.track_active.pop(track,None)
                self.track_bbox_offsets.pop(track,None)
            self.track_actors=kept
        existing={track for track,_,_,_ in self.track_actors}
        data = self.scene.tracks["tracks_data"]
        insert_specs = self.scenario.config.get('insert_assets',[]) if isinstance(self.scenario,HighwayBlockade) else getattr(self.scenario,'insert_asset_specs',getattr(self.scenario,'crash_asset_specs',[]))
        if insert_specs:
            for spec in insert_specs:
                if spec['id'] in data['tracks_id']:continue
                data['tracks_id'].append(spec['id'])
                data['tracks_label_class'].append(spec['semantic_class'])
                data['tracks_poses'].append([[0,0,0,0,0,0,1],[0,0,0,0,0,0,1]])
                data['tracks_timestamps_us'].append([self.scene.start_us,self.scene.end_us])
        lib = self.world.get_blueprint_library()
        for i, track_id in enumerate(data["tracks_id"]):
            if track_id in existing or (required is not None and track_id not in required):
                continue
            label = data["tracks_label_class"][i]
            if label not in ("automobile", "heavy_truck", "bus", "trailer", "person", "rider"):
                continue
            poses = np.array(data["tracks_poses"][i])
            ts = np.array(data["tracks_timestamps_us"][i])
            if len(ts) < 2:
                continue
            name = {"heavy_truck": "vehicle.carlamotors.carlacola", "bus": "vehicle.mitsubishi.fusorosa",
                    "person": "walker.pedestrian.0001"}.get(label, "vehicle.audi.a2")
            bp = lib.find(name)
            if bp.has_attribute("role_name"):
                bp.set_attribute("role_name", "nurec_track_" + track_id)
            matrix = np.eye(4)
            matrix[:3, :3] = Rotation.from_quat(poses[0, 3:]).as_matrix()
            matrix[:3, 3] = poses[0, :3]
            tr = to_transform(self.scene.alignment @ matrix)
            # Spawn in a temporary empty layer, disable physics, then place precisely.
            elevated = carla.Transform(carla.Location(tr.location.x, tr.location.y,
                                                      tr.location.z + 20 + i * 4), tr.rotation)
            actor = self.world.try_spawn_actor(bp, elevated)
            if actor is None:
                self.track_failures.append(track_id)
                continue
            actor.set_simulate_physics(False)
            actor.set_collisions(False)
            elevated.location.z = -1000 - i * 4
            actor.set_transform(elevated)
            self.actors.append(actor)
            box = actor.bounding_box.location
            self.track_bbox_offsets[track_id] = np.array([box.x, box.y, box.z])
            self.track_actors.append((track_id, actor, poses, ts))
            self.track_active[track_id] = False
        self.state['collision_proxy_count']=len(self.track_actors)
        self.state['collision_proxy_scope']='full' if required is None else 'scenario'

    def update_tracks(self, timestamp):
        with self.track_lock:
            return self._update_tracks(timestamp)

    def _update_tracks(self, timestamp):
        dynamic_objects = []
        transforms = []
        with self.scenario.lock:
            scenario_pose = self.scenario.pose()[0] if self.scenario.enabled else None
            has_traffic=isinstance(self.scenario,HighwayBlockade) or getattr(self.scenario,'OVERTAKE_TRIAL',False)
            overrides=self.scenario.traffic_poses() if has_traffic and self.scenario.enabled else {self.scenario.TRACK_ID:scenario_pose} if scenario_pose is not None else {}
            render_scenario = self.scenario.public()
            context_ids=set(getattr(self.scenario,'context_track_ids',()))
        for track_id, actor, poses, ts in self.track_actors:
            override = track_id in overrides
            # Isolate the study stimulus. Other editable cars are absent from
            # both rendering and collisions; static reconstructed context stays.
            suppressed = (scenario_pose is not None and track_id in self.editable_ids and not override
                          and track_id not in context_ids
                          and getattr(self.scenario, 'SUPPRESS_OTHER_TRAFFIC', True))
            active = not suppressed and (override or bool(ts[0] <= timestamp <= ts[-1]))
            if active != self.track_active[track_id]:
                actor.set_collisions(active)
                self.track_active[track_id] = active
                if not active:
                    actor.set_transform(carla.Transform(carla.Location(z=-1000)))
            if not active:
                continue
            if override:
                aligned = overrides[track_id]
                mat = self.scene.inverse_alignment @ aligned
            else:
                k = min(max(int(np.searchsorted(ts, timestamp)) - 1, 0), len(ts) - 2)
                u = float(np.clip((timestamp - ts[k]) / max(ts[k + 1] - ts[k], 1), 0, 1))
                mat = np.eye(4)
                mat[:3, 3] = (1 - u) * poses[k, :3] + u * poses[k + 1, :3]
                mat[:3, :3] = Slerp([0, 1], Rotation.from_quat(poses[k:k+2, 3:]))([u]).as_matrix()[0]
                aligned = self.scene.alignment @ mat
            if track_id in self.editable_ids:
                pose = grpc_pose(mat)
                dynamic_objects.append(proto.DynamicObject(track_id=track_id,
                    pose_pair=proto.PosePair(start_pose=pose, end_pose=pose)))
            # Source cuboid poses describe the bbox centre; CARLA actor origins
            # are near the rear axle/ground. Align the proxy's actual bbox centre.
            left = carla_matrix(aligned)
            left[:3, 3] -= left[:3, :3] @ self.track_bbox_offsets[track_id]
            transform = to_transform(carla_matrix(left))
            if getattr(self.args, 'proxy_update_mode', 'batch') == 'batch':
                transforms.append(carla.command.ApplyTransform(actor.id, transform))
            else:
                actor.set_transform(transform)
        if transforms:
            # Fire-and-forget, as with Actor.set_transform. Waiting for individual
            # responses adds a network round trip to every RGB frame. No tick.
            self.client.apply_batch(transforms, False)
        return dynamic_objects, scenario_pose, render_scenario

    def on_ego_collision(self, event):
        roles={track:role for role,track in self.scenario.crash_roles.items()}
        roles[self.scenario.TRACK_ID]='lead'
        track=next((track for track,actor,_,_ in self.track_actors if actor.id==event.other_actor.id),None)
        if track in roles:
            impulse=event.normal_impulse
            self.scenario.on_collision(roles[track],math.sqrt(impulse.x**2+impulse.y**2+impulse.z**2))

    def settle_after_verified_contact(self, transform):
        # Moving kinematic proxies can inject unbounded impulses. The actual
        # sensor contact remains required; only the subsequent observation is held.
        if not getattr(self.scenario, 'OVERTAKE_TRIAL', False) or not self.scenario.primary_verified:
            return False
        if not self.crash_held:
            anchor = self.pre_contact_transform or transform
            self.ego.set_target_velocity(carla.Vector3D())
            self.ego.set_target_angular_velocity(carla.Vector3D())
            self.ego.apply_control(carla.VehicleControl(brake=1., hand_brake=True))
            self.ego.set_simulate_physics(False)
            self.ego.set_transform(anchor)
            self.crash_held = True
            self.scenario.log('post_collision_vehicle_held', physical_contact_verified=True,
                motion_source='scripted observation hold at last pre-contact CARLA pose; not a free-physics aftermath')
        return True

    def release_collision_hold(self):
        if self.crash_held:
            self.ego.set_transform(self.initial_transform)
            self.ego.set_simulate_physics(True)
        self.crash_held = False
        self.pre_contact_transform = None
        self.state['post_collision_hold'] = False

    def connect_renderer(self):
        grpc.channel_ready_future(self.channel).result(timeout=600)
        cams = self.stub.get_available_cameras(proto.AvailableCamerasRequest(
            scene_id=self.scene.scene_id), timeout=300)
        cam = next(c for c in cams.available_cameras if c.logical_id == self.scene.camera_id)
        self.intrinsics = cam.intrinsics
        if self.high_beam_effect:self.high_beam_effect.configure(self.intrinsics)
        if self.fog_effect:
            self.fog_effect.configure(self.intrinsics)
        config = self.stub.get_server_config(common.Empty(), timeout=20)
        if str(config.server_config.get('enable_editing_actors', '')).lower() != 'true':
            raise RuntimeError('Scenario requires --enable-editing-actors on the dedicated renderer')
        if not renderer_matches(config.server_config, getattr(self.args, 'renderer_backend', 'trained')):
            raise RuntimeError('The requested NuRec renderer differs from the running backend')
        self.state['server_renderer_config'] = dict(config.server_config)
        insert_specs = self.scenario.config.get('insert_assets',[]) if isinstance(self.scenario,HighwayBlockade) else getattr(self.scenario,'insert_asset_specs',getattr(self.scenario,'crash_asset_specs',[]))
        if insert_specs:
            ensure_asset_tracks(self.channel,self.scene.scene_id,self.scene.start_us,self.scene.end_us,
                                insert_specs)
        catalog = self.stub.get_dynamic_objects(proto.AvailableDynamicObjectsRequest(
            scene_id=self.scene.scene_id), timeout=30)
        self.editable_ids = {a.id for a in catalog.dynamic_objects}
        self.track_dimensions={a.id:[a.object_size.size_x,a.object_size.size_y,a.object_size.size_z]
            for a in catalog.dynamic_objects}
        if isinstance(self.scenario,HighwayBlockade):
            wanted=set(self.scenario.config['vehicles'])
            if not wanted.issubset(self.editable_ids):raise RuntimeError('Selected native traffic is not editable: '+str(wanted-self.editable_ids))
            for actor in catalog.dynamic_objects:
                if actor.id in wanted:
                    d=actor.object_size
                    self.scenario.config['vehicles'][actor.id]['size']=[d.size_x,d.size_y,d.size_z]
        lead = next(a for a in catalog.dynamic_objects if a.id == self.scenario.TRACK_ID)
        if self.fog_effect:
            self.fog_effect.configure_lead(self.track_dimensions[self.scenario.TRACK_ID])
        self.scenario.height = lead.object_size.size_z / 2
        if getattr(self.scenario,'ASSET_GROUND_HEIGHT',None) is not None:
            self.scenario.height = self.scenario.ASSET_GROUND_HEIGHT
            self.state['lead_grounding']='replacement asset calibrated relative to its source road'
        elif getattr(self.scenario,'STRAIGHT_TRIAL',False) or getattr(self.scenario,'CALIBRATE_LEAD_HEIGHT',False):
            track=next(row for row in self.track_actors if row[0]==self.scenario.TRACK_ID)
            aligned=[]
            for source_pose in track[2]:
                matrix=np.eye(4)
                matrix[:3,:3]=Rotation.from_quat(source_pose[3:]).as_matrix()
                matrix[:3,3]=source_pose[:3]
                aligned.append(self.scene.alignment@matrix)
            self.scenario.height=recorded_track_height(self.scenario.route,aligned)
            self.state['lead_grounding']='median native track height relative to measured route'
        self.scenario.half_length = lead.object_size.size_x / 2
        if isinstance(self.scenario,(DenseFog,BoundaryWeaving)):
            # Initial bumper gap/lead trajectory must use the selected model's
            # dimensions, including on the first startup before a user reset.
            self.scenario.reset()
        if getattr(self,'defer_initial_tracks',False):
            self.state.update(phase='warming_renderer_before_proxies')
            self.warm_renderer_before_proxies()
            self.setup_tracks()
            actual={a[0] for a in self.track_actors}
            missing=set(self.scenario.config['vehicles'])-actual
            if missing:raise RuntimeError('Missing highway collision proxies after warmup: '+str(sorted(missing)))
            details=dict(self.carla_ready_details,track_actors=len(self.track_actors),initial_proxies_deferred=True)
            (self.run_dir/'carla-ready.json').write_text(json.dumps(details,indent=2),encoding='utf-8')
        if self.scenario.TRACK_ID not in {a[0] for a in self.track_actors}:
            raise RuntimeError('Visible scenario car has no matching CARLA collision actor')
        if getattr(self.scenario,'OVERTAKE_TRIAL',False):
            labels=dict(zip(self.scene.tracks['tracks_data']['tracks_id'],self.scene.tracks['tracks_data']['tracks_label_class']))
            proxies={a[0] for a in self.track_actors}
            self.scenario.configure_crash_traffic([dict(id=a.id,kind=labels.get(a.id),
                length=a.object_size.size_x,width=a.object_size.size_y,height=a.object_size.size_z)
                for a in catalog.dynamic_objects if a.id in proxies])
        ver = self.stub.get_version(common.Empty(), timeout=20)
        (self.run_dir / "renderer-version.txt").write_text(str(ver), encoding="utf-8")
        print("NuRec gRPC connected:", str(ver).strip(), flush=True)

    def warm_renderer_before_proxies(self):
        """Hidden initialization only; first visible/live frame follows all proxies."""
        tr=self.ego.get_transform()
        timestamp=self.scene.source_timestamp(tr)
        overrides=self.scenario.traffic_poses();overrides[self.scenario.TRACK_ID]=self.scenario.pose()[0]
        objects=[]
        for track,mat in overrides.items():
            pose=grpc_pose(self.scene.inverse_alignment@mat)
            objects.append(proto.DynamicObject(track_id=track,pose_pair=proto.PosePair(start_pose=pose,end_pose=pose)))
        eye=grpc_pose(self.scene.camera_pose(tr));width,height=self.render_size
        request=proto.RGBRenderRequest(scene_id=self.scene.scene_id,resolution_w=width,resolution_h=height,
            camera_intrinsics=self.intrinsics,frame_start_us=timestamp,frame_end_us=timestamp+1,
            sensor_pose=proto.PosePair(start_pose=eye,end_pose=eye),dynamic_objects=objects,
            image_format=proto.ImageFormat.JPEG,image_quality=95)
        started=time.monotonic();response=self.stub.render_rgb(request,timeout=300)
        validate_jpeg(response.image_bytes,(width,height),full_decode=True)
        (self.run_dir/'renderer-pre-proxy-warmup.jpg').write_bytes(response.image_bytes)
        (self.run_dir/'renderer-pre-proxy-warmup.json').write_text(json.dumps(dict(actual_nurec_render=True,
            actual_live_driving=False,initialization_only=True,collision_proxy_count=len(self.track_actors),
            dynamic_actor_ids=[a.track_id for a in objects],wall_s=time.monotonic()-started)),encoding='utf-8')

    def control_loop(self):
        previous = time.monotonic()
        speed_integral=0.
        while not self.stop.wait(0.025):
            try:
                now = time.monotonic()
                dt, previous = now - previous, now
                with self.lock:
                    cmd = dict(self.command)
                    if self.ready_for_driving.is_set():self.command["reset"] = False
                    else:cmd["reset"] = False
                if cmd["reset"]:
                    speed_integral=0.
                    self.release_collision_hold()
                    if cmd.get('duration_s') and isinstance(self.scenario, Congestion):
                        self.scenario.set_duration(cmd['duration_s'])
                    self.scenario.reset(enabled=cmd.get('scenario_enabled', self.scenario.enabled))
                    # Free-drive expands lazily; returning to a trial reclaims extras.
                    self.setup_tracks(include_all=not self.scenario.enabled)
                    self.ego.set_target_velocity(carla.Vector3D())
                    self.ego.set_target_angular_velocity(carla.Vector3D())
                    self.ego.set_transform(self.initial_transform)
                tr = self.ego.get_transform()
                if self.settle_after_verified_contact(tr):
                    tr = self.ego.get_transform()
                else:
                    self.pre_contact_transform = tr
                v = self.ego.get_velocity()
                speed = math.sqrt(v.x*v.x + v.y*v.y + v.z*v.z) * 3.6
                index, distance = self.scene.nearest(tr)
                mode = cmd["mode"]
                if not self.ready_for_driving.is_set():mode='paused'
                if self.state["phase"] != "live" or time.monotonic() - self.last_frame_time > 2:
                    mode = "paused"
                crash_trial=getattr(self.scenario,'OVERTAKE_TRIAL',False)
                crash_active=crash_trial and self.scenario.crash_active
                if crash_active and mode=='manual':mode='auto'
                following_speed = self.scenario.advance(dt, mode in ('auto', 'manual'),
                    [tr.location.x, -tr.location.y], speed)
                high_beam=getattr(self.scenario,'high_beam',None)
                if high_beam is not None:
                    on=high_beam.public()['on']
                    light_state=carla.VehicleLightState.Position|carla.VehicleLightState.LowBeam
                    if on:light_state|=carla.VehicleLightState.HighBeam
                    if int(light_state)!=self.last_light_state:
                        self.ego.set_light_state(carla.VehicleLightState(light_state))
                        self.last_light_state=int(light_state)
                # Keep the route boundary stop, but let a pending result finish
                # its observation clock while the actual car is held at the end.
                if self.scenario.completed or index >= len(self.scene.route) - 5:
                    mode = 'paused'
                ctl = carla.VehicleControl()
                if mode == "auto" and index < len(self.scene.route) - 5 and distance < 5:
                    # Pure pursuit reads the actual CARLA pose; never teleports ego along video.
                    lookahead = 5 + speed * 0.22
                    points = self.scene.route[:, :3, 3]
                    j = index
                    while j < len(points) - 1 and np.linalg.norm(points[j, :2] - points[index, :2]) < lookahead:
                        j += 1
                    target = points[j]
                    if crash_active:target=self.scenario.steering_target(lookahead)
                    dx, dy = target[0] - tr.location.x, -target[1] - tr.location.y
                    angle = math.atan2(dy, dx) - math.radians(tr.rotation.yaw)
                    angle = math.atan2(math.sin(angle), math.cos(angle))
                    ctl.steer = float(np.clip(math.atan2(2 * 2.9 * math.sin(angle), lookahead) / .6, -.55, .55))
                    speed_cap=36. if isinstance(self.scenario,HighwayBlockade) else self.args.speed
                    target_speed = speed_cap if following_speed is None else min(speed_cap, following_speed)
                    error = target_speed - speed
                    ctl.throttle = float(np.clip(error * .08, 0., .55))
                    ctl.brake = float(np.clip(-error * .12, 0., .8))
                    if self.scenario.enabled:
                        ctl.brake = min(ctl.brake, .30)
                    if isinstance(self.scenario,(HighwayBlockade,BoundaryWeaving)):
                        # Low-speed feed-forward/integral control avoids a
                        # persistent following-distance error from driveline drag.
                        speed_integral=float(np.clip(speed_integral+error*min(dt,.2),-6.,6.))
                        ctl.throttle=float(np.clip(.18+.07*error+.03*speed_integral,0.,.7))
                        ctl.brake=float(np.clip(-error*.12,0.,.3)) if error<-.6 else 0.
                        if target_speed<.1:ctl.throttle,ctl.brake=0.,.3
                elif mode == "manual" and time.monotonic() - cmd["last_input"] < .6 and distance < 6:
                    keys = cmd["keys"]
                    ctl.throttle = .5 if keys.get("w") else 0.
                    ctl.brake = .8 if keys.get("s") or keys.get(" ") else 0.
                    ctl.steer = (-.35 if keys.get("a") else 0.) + (.35 if keys.get("d") else 0.)
                    if speed > 45:
                        ctl.throttle = 0.
                else:
                    ctl.brake = 1.
                    speed_integral=0.
                # Manual input cannot drive through the controlled lead car.
                if self.scenario.outcome.phase in ('stopping', 'complete'):
                    ctl.throttle, ctl.brake = 0., .30
                if self.scenario.enabled and self.scenario.gap < 5 and not crash_active:
                    ctl.throttle, ctl.brake = 0., 1.
                if crash_active and self.scenario.crash_brake:
                    ctl.throttle,ctl.brake=0.,1.
                self.ego.apply_control(ctl)
                self.state.update(speed_kph=round(speed, 1), mode=mode, route_index=index,
                    cross_track_m=round(distance, 2), route_end=index >= len(self.scene.route) - 5 or self.scenario.completed,
                    scenario=self.scenario.public(),
                    post_collision_hold=self.crash_held,
                    carla_frame=self.world.get_snapshot().frame,
                    carla_position=[tr.location.x, tr.location.y, tr.location.z])
            except Exception as e:
                self.state.update(error=str(e))
                self.stop.set()

    def render_once(self, label=None):
        frame_started = time.perf_counter()
        with self.lock:
            width, height = self.render_size
            quality = self.quality
        snapshot = self.world.get_snapshot()
        ego_snapshot = snapshot.find(self.ego.id)
        tr = ego_snapshot.get_transform() if ego_snapshot is not None else self.ego.get_transform()
        index, distance = self.scene.nearest(tr)
        timestamp = self.scene.source_timestamp(tr)
        dynamic_objects, scenario_pose, render_scenario = self.update_tracks(timestamp)
        tracks_done = time.perf_counter()
        cam_matrix = self.scene.camera_pose(tr)
        pose = grpc_pose(cam_matrix)
        render_objects=dynamic_objects
        if self.args.scenario_load=='essential' and isinstance(self.scenario,HighwayBlockade) and self.scenario.enabled:
            angle=getattr(self.intrinsics.ftheta_param,'max_angle',None)
            render_objects=visible_fast_traffic(dynamic_objects,cam_matrix,angle,self.scenario.config['vehicles'],
                {self.scenario.TRACK_ID,*self.scenario.large_ids})
        # Explicit poses follow each active proxy. Scenario 2 isolates one lead
        # stimulus; free-drive preserves the measured editable traffic timeline.
        req = proto.RGBRenderRequest(scene_id=self.scene.scene_id,
            resolution_w=width, resolution_h=height,
            camera_intrinsics=self.intrinsics, frame_start_us=timestamp, frame_end_us=timestamp + 1,
            sensor_pose=proto.PosePair(start_pose=pose, end_pose=pose),
            dynamic_objects=render_objects,
            image_format=proto.ImageFormat.JPEG, image_quality=95)
        started = time.perf_counter()
        native_ranges=None;native_fog_applied=False
        if self.fog_effect and render_scenario['fog']['beta']>0:
            response,rpc_call=self.stub.render_rgb.with_call(req,timeout=300,metadata=(("x-nurec-range","1"),
                ("x-nurec-fog",json.dumps([render_scenario["fog"]["beta"],render_scenario["elapsed_s"]]))))
            hint=next((m.value for m in rpc_call.trailing_metadata() if m.key=="nurec-range-bin"),None)
            native_ranges=decode_range_hint(hint,timestamp)
            native_fog_applied=any(m.key=="nurec-fog" and m.value=="1" for m in rpc_call.trailing_metadata())
        else:
            response = self.stub.render_rgb(req, timeout=300)
        elapsed = time.perf_counter() - started
        rpc_done = time.perf_counter()
        jpeg = response.image_bytes
        beam_record=None
        if self.high_beam_effect:
            signal=render_scenario['high_beam'];unlit=jpeg
            ego_source=ground=None;actors=[]
            if signal['on']:
                ego_source=self.scene.inverse_alignment@carla_matrix(np.array(tr.get_matrix()))
                wp=self.map.get_waypoint(tr.location,project_to_road=True,lane_type=carla.LaneType.Driving)
                ground=self.scene.inverse_alignment@np.array([tr.location.x,-tr.location.y,wp.transform.location.z,1.])
                for actor in dynamic_objects:
                    p=actor.pose_pair.start_pose;m=np.eye(4)
                    m[:3,:3]=Rotation.from_quat([p.quat.x,p.quat.y,p.quat.z,p.quat.w]).as_matrix()
                    m[:3,3]=[p.vec.x,p.vec.y,p.vec.z]
                    actors.append((m,self.scenario.config['vehicles'][actor.track_id]['size']))
            effect_started=time.perf_counter()
            jpeg,beam_record=self.high_beam_effect.apply(jpeg,cam_matrix,ego_source,ground[:3] if ground is not None else None,self.scene.inverse_alignment[:3,2],actors,signal)
            beam_record['effect_ms']=round((time.perf_counter()-effect_started)*1000,2)
            beam_record['carla_light_state']=int(self.ego.get_light_state())
            if signal['on']:
                prefix=f"highbeam-{render_scenario['session']}-{signal['sequence']}-{signal['stage']}"
                if not (self.run_dir/(prefix+'-lit.jpg')).exists():
                    (self.run_dir/(prefix+'-base.jpg')).write_bytes(unlit)
                    (self.run_dir/(prefix+'-lit.jpg')).write_bytes(jpeg)
        fog_record=None
        if self.fog_effect:
            started_fog=time.perf_counter()
            lead_source=(self.scene.inverse_alignment@scenario_pose) if scenario_pose is not None else None
            if native_fog_applied:
                fog_record=dict(applied=True,stage=render_scenario['fog']['stage'],beta=render_scenario['fog']['beta'],
                    method='same-frame native range + GPU Beer-Lambert compositing',approximate=True,
                    range_source='native_same_frame',native_composite=True,points=0,range_grid=[width,height])
            else:
                jpeg,fog_record=self.fog_effect.apply(jpeg,cam_matrix,lead_source,render_scenario,native_ranges=native_ranges)
            fog_record['bridge_bookkeeping_ms']=round((time.perf_counter()-started_fog)*1000,2)
            fog_record['composite_ms']=None if native_fog_applied else fog_record['bridge_bookkeeping_ms']
            fog_record['composite_location']='renderer_gpu' if native_fog_applied else 'bridge_cpu'
            fog_record['gpu_composite_included_in_rpc']=native_fog_applied
        # Keep structure/size checks on every frame. Fully decode startup,
        # resize, labelled evidence and periodic audits instead of duplicating
        # the viewer's full RGB decode on every unchanged-resolution frame.
        audit=bool(label or self.validated_image_size!=(width,height)
                   or time.monotonic()-self.rgb_audit_time>=2.)
        dimensions=validate_jpeg(jpeg,(width,height),full_decode=audit)
        self.validated_image_size=dimensions
        if audit:self.rgb_audit_time=time.monotonic()
        validation_done = time.perf_counter()
        timings = dict(prepare_ms=(tracks_done-frame_started)*1000,
            request_ms=(started-tracks_done)*1000, rpc_ms=elapsed*1000,
            postprocess_ms=(validation_done-rpc_done)*1000)
        record = {"id": self.frame_id + 1, "monotonic": time.monotonic(),
            "post_collision_hold": self.crash_held,
            "carla_frame": snapshot.frame,
            "carla_frame_on_response": self.world.get_snapshot().frame,
            "carla_transform": np.array(tr.get_matrix()).tolist(),
            "camera_pose": cam_matrix.tolist(), "scene_timestamp_us": timestamp,
            "route_index": index, "cross_track_m": distance, "rpc_ms": elapsed * 1000,
            "jpeg_sha256": hashlib.sha256(jpeg).hexdigest(), "dimensions": dimensions,
            "label": label, "quality": quality, "dynamic_actor_ids": [a.track_id for a in render_objects],
            "simulated_actor_ids": [a.track_id for a in dynamic_objects],
            "full_rgb_decode_audit": audit,
            "scenario": render_scenario,
            "timings": timings,
            "scenario_cuboid_pose": scenario_pose.tolist() if scenario_pose is not None else None}
        if fog_record is not None:record['fog_effect']=fog_record
        if beam_record is not None:record['high_beam_effect']=beam_record
        self.trace.write(json.dumps(record) + "\n")
        timings['trace_ms'] = (time.perf_counter()-validation_done)*1000
        if label:
            (self.run_dir / (label + ".jpg")).write_bytes(jpeg)
            (self.run_dir / (label + ".json")).write_text(json.dumps(record, indent=2), encoding="utf-8")
        with self.frame_event:
            self.jpeg = jpeg
            self.frame_id += 1
            self.last_frame_time = time.monotonic()
            self.frame_event.notify_all()
        if getattr(self.scenario,'OVERTAKE_TRIAL',False):
            self.scenario.acknowledge_crash_frame(render_scenario['session'],render_scenario['crash']['phase'])
        if self.high_beam_effect:
            signal=render_scenario['high_beam']
            physical_on=bool(beam_record['carla_light_state']&int(carla.VehicleLightState.HighBeam))
            if physical_on==signal['on']:
                self.scenario.acknowledge_high_beam(render_scenario['session'],signal['sequence'],signal['stage'])
        self.state.update(phase="live", frames=self.frame_id, rpc_ms=round(elapsed * 1000),
                          width=dimensions[0], height=dimensions[1], quality=quality, error=None)
        timings['total_ms'] = (time.perf_counter()-frame_started)*1000
        self.state['frame_timings_ms'] = {key: round(value, 2) for key, value in timings.items()}
        return record

    def render_loop(self):
        try:
            self.connect_renderer()
            self.state.update(phase="warming_renderer")
            self.render_once("first-live-frame")
            self.ready_for_driving.set()
            while not self.stop.is_set():
                start = time.monotonic()
                self.render_once()
                with self.lock:
                    idle = self.command['mode'] == 'paused' and self.frame_id >= 15
                self.state['render_cadence'] = 'idle' if idle else 'live'
                period = 1. if idle else 1 / self.args.fps
                self.render_wake.wait(max(0, period - (time.monotonic() - start)))
                self.render_wake.clear()
        except Exception:
            self.state.update(phase="error", error=traceback.format_exc())
            (self.run_dir / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
            print(traceback.format_exc(), flush=True)

    def close(self):
        self.stop.set()
        self.render_wake.set()
        for actor in reversed(self.actors):
            try:
                actor.destroy()
            except RuntimeError:
                pass
        if self.restore_no_rendering is not None:
            try:
                settings = self.world.get_settings()
                settings.no_rendering_mode = self.restore_no_rendering
                self.world.apply_settings(settings)
            except RuntimeError:
                pass
        self.trace.close()
        self.scenario.events.close()
        self.channel.close()


def make_handler(bridge):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            path = urlparse(self.path).path
            if path == '/navigation':
                data, content = navigation_html(), 'text/html; charset=utf-8'
            elif path.startswith('/api/narration/audio/'):
                name=path.removeprefix('/api/narration/audio/')
                try:
                    if not name.endswith('.wav'):raise ValueError('Invalid audio')
                    data=narration_audio_path(name[:-4]).read_bytes();content='audio/wav'
                except (OSError,ValueError,KeyError,AssertionError):
                    self.send_error(503,'Sohee recording is not ready');return
            elif path == '/api/state':
                data, content = json.dumps(bridge.navigation.state(), ensure_ascii=False).encode('utf-8'), 'application/json; charset=utf-8'
            elif path == '/api/atlas':
                data, content = json.dumps(bridge.navigation.atlas()).encode(), 'application/json'
            elif path == '/api/library':
                from passenger_music import library
                data, content = json.dumps({'tracks':library()},ensure_ascii=False).encode(), 'application/json; charset=utf-8'
            elif path.startswith('/media/'):
                from passenger_music import stream
                stream(self,path.removeprefix('/media/'));return
            elif path == '/api/reply':
                query = parse_qs(urlparse(self.path).query)
                data = json.dumps(bridge.navigation.reply(query.get('session',[''])[0], query.get('id',[''])[0]),ensure_ascii=False).encode('utf-8')
                content = 'application/json; charset=utf-8'
            elif path == "/":
                data = navigation_html() if bridge.args.profile=='fog' else (ROOT / "viewer.html").read_bytes()
                content = "text/html; charset=utf-8"
            elif path == "/state":
                public_state = dict(bridge.state)
                public_state['scenario'] = bridge.scenario.public()
                data = json.dumps(public_state).encode()
                content = "application/json"
            elif path == "/frame.jpg":
                if bridge.jpeg is None:
                    self.send_error(503, "Renderer is warming")
                    return
                data, content = bridge.jpeg, "image/jpeg"
            elif path == "/stream":
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                last = -1
                try:
                    while not bridge.stop.is_set():
                        with bridge.frame_event:
                            bridge.frame_event.wait_for(lambda: bridge.frame_id != last or bridge.stop.is_set(), 3)
                            jpeg, last = bridge.jpeg, bridge.frame_id
                        if jpeg:
                            self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " +
                                str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n")
                            self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass
                return
            else:
                asset = static_asset(path)
                if asset is None:
                    self.send_error(404)
                    return
                data, content = asset
            self.send_response(200)
            self.send_header("Content-Type", content)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            if self.path not in ("/control", '/api/command'):
                self.send_error(404)
                return
            if self.headers.get("Origin") not in (None, f"http://127.0.0.1:{bridge.args.web_port}",
                                                   f"http://localhost:{bridge.args.web_port}"):
                self.send_error(403)
                return
            size = int(self.headers.get("Content-Length", "0"))
            if size > 4096:
                self.send_error(413)
                return
            try:
                body = json.loads(self.rfile.read(size))
                if self.path == '/api/command':
                    result = bridge.navigation.command(body)
                    bridge.render_wake.set()
                    data = json.dumps(result,ensure_ascii=False).encode('utf-8')
                    self.send_response(200)
                    self.send_header('Content-Type','application/json; charset=utf-8')
                    self.send_header('Content-Length',str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                if 'interaction' in body:
                    result = bridge.scenario.interaction(body['interaction'], body.get('session'))
                    bridge.render_wake.set()
                    data = json.dumps(result, ensure_ascii=False).encode('utf-8')
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json; charset=utf-8')
                    self.send_header('Content-Length', str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                with bridge.lock:
                    if 'duration_s' in body:
                        if not isinstance(bridge.scenario, Congestion) or body['duration_s'] not in (300, 450, 600):
                            raise ValueError('이 체험에서는 5분, 7분 30초, 10분을 선택할 수 있습니다.')
                        bridge.command.update(duration_s=body['duration_s'], reset=True, mode='paused')
                    if body.get("quality") in QUALITY_PRESETS:
                        bridge.quality = body["quality"]
                        bridge.render_size = QUALITY_PRESETS[bridge.quality]
                    if body.get("mode") in ("auto", "paused", "manual"):
                        bridge.command["mode"] = body["mode"]
                    if "keys" in body:
                        bridge.command["keys"] = {k: bool(v) for k, v in body["keys"].items()
                                                  if k in ("w", "a", "s", "d", " ")}
                        bridge.command["last_input"] = time.monotonic()
                    if body.get("reset"):
                        bridge.command.update(reset=True, mode="paused")
                    if body.get('scenario') in ('drowsy_night', 'free_drive'):
                        bridge.command.update(reset=True, mode='paused',
                            scenario_enabled=body['scenario'] == 'drowsy_night')
                bridge.render_wake.set()
                self.send_response(204)
                self.end_headers()
            except (ValueError, TypeError) as exc:
                data = json.dumps({'error':str(exc)},ensure_ascii=False).encode('utf-8')
                self.send_response(400)
                self.send_header('Content-Type','application/json; charset=utf-8')
                self.send_header('Content-Length',str(len(data)))
                self.end_headers()
                self.wfile.write(data)
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', choices=['night', 'congestion','fog'], default='night')
    parser.add_argument('--night-mode', choices=['straight','overtake-crash'], default='straight')
    parser.add_argument("--carla-port", type=int, default=2016)
    parser.add_argument("--web-port", type=int, default=8774)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--fps", type=float, default=30)
    parser.add_argument('--proxy-update-mode', choices=['direct','batch'], default='batch')
    parser.add_argument('--scenario-load',choices=['full','essential'],default='essential')
    parser.add_argument('--traffic-load',choices=['standard','compact'],default='standard')
    parser.add_argument("--speed", type=float, default=30)
    parser.add_argument('--physics-only', action='store_true',
                        help='Skip unused CARLA drawing; keep separate NuRec RGB, DX12 and async physics')
    parser.add_argument('--renderer-backend', choices=['trained','nrend','gsplat','gsplat-native'], default='trained')
    args = parser.parse_args()
    bridge = Bridge(args)
    server = ThreadingHTTPServer(("127.0.0.1", args.web_port), make_handler(bridge))
    threading.Thread(target=bridge.control_loop, daemon=True).start()
    threading.Thread(target=bridge.render_loop, daemon=True).start()
    print(f"Viewer http://127.0.0.1:{args.web_port}/ ; run {bridge.run_dir}", flush=True)
    try:
        server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        bridge.close()


if __name__ == "__main__":
    main()
