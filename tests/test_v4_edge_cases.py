import unittest,tempfile,json
from pathlib import Path
import numpy as np
from core.derived_v4 import append_record,read_latest,ground_record
from core.pointcloud import display_points
from core.ground_v4 import segment_ground

class V4EdgeTests(unittest.TestCase):
    def test_failed_json_does_not_leave_new_artifact(self):
        root=Path(tempfile.mkdtemp(prefix='v4-immutable-'));before=list(root.rglob('*.json'))
        with self.assertRaises(ValueError):append_record(root,'a'*32,'records',{'bad':float('nan')})
        self.assertEqual(list(root.rglob('*.json')),before)
    def test_latest_reader_ignores_incomplete_record(self):
        root=Path(tempfile.mkdtemp(prefix='v4-immutable-'));append_record(root,'a'*32,'records',{'ok':1});folder=root/'a'*0 if False else root/('a'*32)/'v4'/'records'
        with (folder/'99999999999999999999-incomplete.json').open('x') as f:f.write('{')
        self.assertEqual(read_latest(root,'a'*32,'records'),{'ok':1})
    def test_mask_follows_display_indices_over_100k(self):
        rng=np.random.default_rng(5);xy=rng.uniform([-4,-4],[4,4],(100003,2));pts=np.column_stack((xy,np.zeros(len(xy)),np.ones(len(xy)))).astype('float32');root=Path(tempfile.mkdtemp(prefix='v4-sample-'))
        r=ground_record(root,'a'*32,pts);self.assertEqual(len(r['display_mask']),len(display_points(pts)));self.assertEqual(r['display_indices'],list(range(0,len(pts),2)))
    def test_stacked_surface_preserves_upper_returns(self):
        rng=np.random.default_rng(8);xy=rng.uniform([-4,-4],[4,4],(3000,2));floor=np.column_stack((xy,np.zeros(3000),np.ones(3000)));upper=np.column_stack((xy,np.full(3000,3),np.ones(3000)));r=segment_ground(np.vstack((floor,upper)))
        self.assertGreater(np.mean(r['mask'][:3000]==1),.9);self.assertEqual(np.sum(r['mask'][3000:]==1),0)
