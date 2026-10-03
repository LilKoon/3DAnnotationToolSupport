import unittest
import numpy as np
from core.ground_v4 import segment_ground, ground_surface, ground_contact
from core.audit_v4 import audit_input

class GroundV4Tests(unittest.TestCase):
    def fixture(self):
        rng=np.random.default_rng(42)
        xy=rng.uniform([-10,-8],[10,8],(10000,2))
        road=np.column_stack((xy,-1.5+.06*xy[:,0]+rng.normal(0,.008,len(xy)),np.ones(len(xy))))
        obj=np.column_stack((rng.uniform([2,0],[3,1],(300,2)),rng.uniform(-.8,1,300),np.ones(300)))
        return np.vstack((road,obj)).astype('float32')
    def test_slope_preserves_objects_and_input(self):
        pts=self.fixture();before=pts.copy();result=segment_ground(pts)
        np.testing.assert_array_equal(pts,before)
        self.assertGreater(np.mean(result['mask'][:10000]==1),.9)
        self.assertLess(np.mean(result['mask'][10000:]==1),.03)
    def test_sparse_and_vertical_unknown(self):
        r=segment_ground(np.array([[0,0,0,1],[0,0,2,1],[8,8,0,1]],dtype='float32'))
        self.assertTrue(np.all(r['mask']==0))
    def test_surface_no_bridge_across_empty_cells(self):
        r=segment_ground(self.fixture());surface=ground_surface(r)
        self.assertGreater(len(surface),0)
        for triangle in surface:
            self.assertLessEqual(np.ptp(np.array(triangle)[:,:2],axis=0).max(),2.01)
    def test_box_ground_contact(self):
        from core.geometry import Cuboid
        r=segment_ground(self.fixture())
        box=Cuboid(id='x',label='car',center=[0,0,-.5],size=[2,2,2])
        self.assertAlmostEqual(ground_contact(box,r)['clearance_m'],0,delta=.05)
    def test_audit_does_not_claim_units_or_calibration(self):
        audit=audit_input(self.fixture(),{'cameras':[{'name':'front.png','index':0}]})
        self.assertFalse(audit['units_confirmed']);self.assertFalse(audit['fusion_ready'])
        self.assertEqual(audit['camera_count'],1)
    def test_invalid_parameters(self):
        with self.assertRaises(ValueError): segment_ground(self.fixture(),cell_size=-1)

if __name__=='__main__':unittest.main()
