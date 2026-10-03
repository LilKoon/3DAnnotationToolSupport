import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np

from core.mac_lidar import mac_model_points, pillars, anchors, decode_deltas, suppress, MacLidarRuntime
from core.detector_service import DetectorService
from core.lidar_presets import GUIDELINE_LABELS


class MacLidarTests(unittest.TestCase):
    def test_checkpoint_feature_semantics_and_no_input_mutation(self):
        points = np.array([[1,2,0,255],[3,4,-1,10]],dtype=np.float32)
        original = points.copy()
        pp = mac_model_points(points,'pointpillars-nuscenes',.5)
        cp = mac_model_points(points,'centerpoint-nuscenes',.5)
        np.testing.assert_array_equal(pp[:,3],0)
        np.testing.assert_array_equal(cp[:,3],points[:,3]*.5)
        np.testing.assert_array_equal(cp[:,4],0)
        np.testing.assert_array_equal(points,original)

    def test_first_occupied_voxel_first_points_cap_and_padding(self):
        # First occupied cell deliberately has larger X than the second cell.
        points = np.array([[10,1,0,i] for i in range(70)]+[[0,0,0,200]],dtype=np.float32)
        prepared = mac_model_points(points,'centerpoint-nuscenes')
        features,coords,counts = pillars(prepared,'centerpoint-nuscenes')
        np.testing.assert_array_equal(counts,[20,1])
        np.testing.assert_array_equal(features[0,:,3],np.arange(20))
        np.testing.assert_array_equal(features[1,1:],0)
        self.assertGreater(coords[0,0],coords[1,0])
        limited,_,count = pillars(prepared,'centerpoint-nuscenes',max_voxels=1)
        self.assertEqual(len(limited),1)
        np.testing.assert_array_equal(count,[20])

    def test_anchor_grid_geometric_z_and_direction(self):
        prior = anchors(2,2,1)
        np.testing.assert_allclose(prior[0,:3],[-25,-25,-1.8])
        np.testing.assert_allclose(prior[8,:2],[25,-25])
        box = decode_deltas(prior[:2],np.zeros((2,9)),np.array([0,1]))
        np.testing.assert_allclose(box[:,2],-1.3)
        np.testing.assert_allclose(box[:,3:6],prior[:2,3:6])
        np.testing.assert_allclose(box[1,6],1.57+np.pi,atol=1e-6)

    def test_circle_uses_squared_distance_and_bev_rotation(self):
        boxes = np.array([[0,0,0,4,1,1,0],[1.5,0,0,4,1,1,0],[3,0,0,4,1,1,0]],dtype=float)
        scores = np.array([.9,.8,.7])
        self.assertEqual(suppress(boxes,scores,circle=4),[0,2])
        rotated = boxes[:2].copy();rotated[1,:2]=0;rotated[1,6]=np.pi/2
        self.assertEqual(suppress(rotated,scores[:2],threshold=.2),[0,1])

    def test_mac_settings_and_validated_boxes_use_local_runtime(self):
        service = DetectorService(Path(tempfile.mkdtemp(prefix='v3-mac-settings-')))
        with patch('core.detector_service.platform.system',return_value='Darwin'):
            self.assertEqual(service.settings()['mode'],'mac')
        service.configure('mac','',None,1)
        ready = [{'id':model,'classes':GUIDELINE_LABELS,'ready':True,'reason':'MPS verified'} for model in ['pointpillars-nuscenes','centerpoint-nuscenes']]
        box = {'label':'car','center':[1,2,0],'size':[4,2,1.5],'yaw':0,'confidence':.8}
        with patch.object(service.mac_runtime,'verify',return_value=ready), patch.object(service.mac_runtime,'infer',return_value=[box]) as inference:
            result = service.infer(np.array([[1,2,0,10]]),'pointpillars-nuscenes',.3)
        self.assertEqual(result[0].label,'car')
        self.assertEqual(result[0].status,'pending')
        inference.assert_called_once()

    def test_real_checkpoints_all_tensors_consumed_and_finite(self):
        runtime = MacLidarRuntime()
        points = np.array([[5,2,0,10],[5.1,2.1,.2,20],[10,-3,-1,5]],dtype=np.float32)
        for model_id in ['pointpillars-nuscenes','centerpoint-nuscenes']:
            boxes = runtime.infer(points,model_id,.1,device='cpu')
            self.assertTrue(all(box['label'] in GUIDELINE_LABELS and np.isfinite(box['center']).all() for box in boxes))
            network = runtime.models[(model_id,'cpu')]
            self.assertEqual(set(network.weights)-network.used,{key for key in network.weights if key.endswith('.num_batches_tracked')})


if __name__=='__main__':
    unittest.main()
