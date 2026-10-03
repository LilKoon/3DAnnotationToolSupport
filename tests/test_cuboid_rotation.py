import unittest
from core.geometry import Cuboid,cvat_points,parse_cvat_points
from pydantic import ValidationError

class CuboidRotationTests(unittest.TestCase):
    def test_roll_pitch_yaw_roundtrip_and_legacy_defaults(self):
        box=Cuboid(id='a',label='car',center=[1,2,3],size=[4,2,1],roll=.2,pitch=-.3,yaw=.4)
        points=cvat_points(box)
        result=parse_cvat_points('a','car',points,0)
        for actual,expected in zip((result.roll,result.pitch,result.yaw),(.2,-.3,.4)):
            self.assertAlmostEqual(actual,expected)
        for field in ['roll','pitch']:
            with self.assertRaises(ValidationError):Cuboid(**{**box.model_dump(),field:float('nan')})
        legacy=Cuboid(id='b',label='car',center=[0,0,0],size=[1,1,1])
        self.assertEqual((legacy.roll,legacy.pitch),(0,0))
