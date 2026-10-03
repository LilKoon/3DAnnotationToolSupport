import unittest
import numpy as np
from core.camera_v4 import Calibration,project_points,project_box,associate
from core.geometry import Cuboid

class CameraTests(unittest.TestCase):
    def calibration(self,**kwargs):
        return Calibration(K=[[100,0,100],[0,100,100],[0,0,1]],T_camera_from_lidar=np.eye(4).tolist(),width=200,height=200,**kwargs)
    def test_projection_and_behind_camera(self):
        uv,depth,valid=project_points(np.array([[0,0,10],[1,0,10],[0,0,-2]]),self.calibration())
        np.testing.assert_allclose(uv[:2],[[100,100],[110,100]]);self.assertEqual(valid.tolist(),[True,True,False])
    def test_invalid_rigid_matrix_or_intrinsics(self):
        with self.assertRaises(ValueError):Calibration(K=[[0,0,0],[0,1,0],[0,0,1]],T_camera_from_lidar=np.eye(4).tolist(),width=200,height=200)
        bad=np.eye(4);bad[0,0]=-1
        with self.assertRaises(ValueError):Calibration(K=[[100,0,100],[0,100,100],[0,0,1]],T_camera_from_lidar=bad.tolist(),width=200,height=200)
    def test_near_plane_clipping(self):
        b=Cuboid(id='x',label='car',center=[0,0,.2],size=[1,1,1])
        r=project_box(b,self.calibration());self.assertIsNotNone(r);self.assertTrue(np.isfinite(r['bbox']).all())
        b.center=[0,0,-5];self.assertIsNone(project_box(b,self.calibration()))
    def test_distortion_changes_pixel(self):
        a=project_points(np.array([[2,0,5]]),self.calibration())[0]
        b=project_points(np.array([[2,0,5]]),self.calibration(distortion=[.2,0,0,0,0]))[0]
        self.assertGreater(b[0,0],a[0,0])
    def test_association_requires_review_pairing_and_class(self):
        box=Cuboid(id='a',label='car',center=[0,0,10],size=[2,2,2])
        detections=[{'id':'d','label':'car','bbox':[88,88,112,112],'confidence':.9}]
        r=associate([box],detections,self.calibration(),{'car':'car'});self.assertEqual(r[0]['status'],'reference_only')
        cal=self.calibration(reviewed=True,frame_pairing='confirmed')
        r=associate([box],detections,cal,{'car':'car'});self.assertEqual(r[0]['box_id'],'a')
        self.assertEqual(associate([box],detections,cal,{'car':'truck'})[0]['status'],'unmatched')
    def test_ambiguous_match_keeps_unknown(self):
        cal=self.calibration(reviewed=True,frame_pairing='confirmed')
        boxes=[Cuboid(id=x,label='car',center=[0,0,10],size=[2,2,2]) for x in ['a','b']]
        r=associate(boxes,[{'id':'d','label':'car','bbox':[88,88,112,112]}],cal,{'car':'car'})
        self.assertEqual(r[0]['status'],'ambiguous')
