"""Geographic alignment and real actor map placement must not be mirrored."""
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from map_context import ecef,georeference_origin,geographic_to_carla,carla_to_geographic,load_context
from prepare_map_context import assemble_rings


class GeographicContext(unittest.TestCase):
    def test_wgs84_equatorial_reference_and_roundtrip(self):
        np.testing.assert_allclose(ecef(0.,0.),[6378137.,0.,0.],atol=1e-6)
        np.testing.assert_allclose(geographic_to_carla(0.,.00001,(0.,0.,0.)),[1.113194908,0.],atol=1e-6)
        np.testing.assert_allclose(geographic_to_carla(.00001,0.,(0.,0.,0.)),[0.,-1.105742758],atol=1e-6)
        origin=(37.3,-121.9,0.)
        latitude,longitude=carla_to_geographic(500.,-300.,origin)
        self.assertGreater(latitude,origin[0]);self.assertGreater(longitude,origin[1])
        np.testing.assert_allclose(geographic_to_carla(latitude,longitude,origin),[500.,-300.],atol=.001)
    def test_recorded_georeference_syntax(self):
        self.assertEqual(georeference_origin('+proj=tmerc +lat_0=37 +lon_0=-121 +=alt_0=12'),(37.,-121.,12.))
        with self.assertRaises(ValueError):georeference_origin('+lat_0=37')
    def test_missing_cache_is_optional_but_wrong_scene_cache_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'live';root.mkdir()
            with patch('map_context.ROOT',root):
                self.assertEqual(load_context(SimpleNamespace(scene_id='one'))['buildings'],[])
                folder=root.parent/'cache/map-context';folder.mkdir(parents=True)
                (folder/'one.json').write_text('{"scene_id":"two","coordinate_frame":"carla_xy"}')
                with self.assertRaises(ValueError):load_context(SimpleNamespace(scene_id='one'))
    def test_multipolygon_members_join_without_fabricating_open_polygons(self):
        ring=assemble_rings([[(0,0),(1,0)],[(1,1),(1,0)],[(1,1),(0,1),(0,0)]])
        self.assertEqual(len(ring),1);self.assertEqual(ring[0][0],ring[0][-1])
        self.assertEqual(assemble_rings([[(0,0),(1,0),(1,1)]]),[])


if __name__=='__main__':unittest.main()
