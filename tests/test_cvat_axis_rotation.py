import unittest
from itertools import permutations,product
import numpy as np
from core.geometry import Cuboid,cvat_oriented_box,cvat_points,parse_cvat_points,rotation_matrix


def matrix(box):
    r,p,y=box.roll,box.pitch,box.yaw
    cr,sr,cp,sp,cy,sy=np.cos(r),np.sin(r),np.cos(p),np.sin(p),np.cos(y),np.sin(y)
    return np.array([[cy*cp,cy*sp*sr-sy*cr,cy*sp*cr+sy*sr],[sy*cp,sy*sp*sr+cy*cr,sy*sp*cr-cy*sr],[-sp,cp*sr,cp*cr]])

class CVATAxisRotationTests(unittest.TestCase):
    def test_all_orders_and_signs_match_visible_axes_and_preserve_geometry(self):
        for order in permutations(range(3)):
            for signs in product([-1,1],repeat=3):
                box=Cuboid(id='a',label='car',center=[1,2,3],size=[4,2,1],yaw=.4,pitch=.2,roll=-.3,axis_order=order,axis_signs=signs)
                target=matrix(box)[:,order]*signs
                if np.linalg.det(target)<0:
                    with self.assertRaisesRegex(ValueError,'tay trái'):cvat_oriented_box(box)
                    continue
                exported=cvat_oriented_box(box)
                np.testing.assert_allclose(matrix(exported),target,atol=1e-7)
                self.assertEqual(exported.axis_order,[0,1,2])
                def corners(b):return sorted(tuple(np.round(np.asarray(b.center)+matrix(b)@(np.asarray(s)*b.size/2),8)) for s in product([-1,1],repeat=3))
                self.assertEqual(corners(box),corners(exported))
                imported=parse_cvat_points('a','car',cvat_points(exported),0)
                np.testing.assert_allclose(matrix(imported),target,atol=1e-7)
                np.testing.assert_allclose(rotation_matrix(*cvat_points(exported)[3:6],order='XYZ'),target,atol=1e-7)

    def test_vertical_axis_gimbal_case(self):
        box=Cuboid(id='a',label='car',center=[0,0,0],size=[4,2,1],axis_order=[2,1,0],axis_signs=[1,1,-1])
        result=cvat_oriented_box(box)
        np.testing.assert_allclose(matrix(result),matrix(box)[:,box.axis_order]*box.axis_signs,atol=1e-7)
