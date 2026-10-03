import unittest
import numpy as np
from core.geometry import Cuboid
from core.measurements_v4 import measure,footprint_xy

class MeasurementsTests(unittest.TestCase):
    def box(self,id,x,y=0,**kwargs):return Cuboid(id=id,label='car',center=[x,y,0],size=[2,2,2],**kwargs)
    def test_known_gap_and_center(self):
        r=measure(self.box('a',0),self.box('b',5));self.assertAlmostEqual(r['center_3d'],5);self.assertAlmostEqual(r['gap_xy'],3)
    def test_rotated_and_overlapping(self):
        r=measure(self.box('a',0,yaw=np.pi/4),self.box('b',5));self.assertAlmostEqual(r['gap_xy'],4-np.sqrt(2))
        self.assertEqual(measure(self.box('a',0),self.box('b',.5))['gap_xy'],0)
    def test_pitch_roll_uses_all_corners(self):
        p=footprint_xy(self.box('a',0,pitch=np.pi/4));self.assertAlmostEqual(np.ptp(p[:,0]),2*np.sqrt(2))
    def test_sensor_distance_is_origin_to_center(self):self.assertAlmostEqual(measure(self.box('a',3,4))['sensor_center_3d'],5)
