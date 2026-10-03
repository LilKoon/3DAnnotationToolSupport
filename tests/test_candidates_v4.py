import unittest,tempfile
from pathlib import Path
from io import BytesIO
from unittest.mock import patch
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient
from core.store import SessionStore
from core.candidates_v4 import candidates
from core.camera_v4 import Calibration

class CandidateTests(unittest.TestCase):
    def setup_cloud(self):
        rng=np.random.default_rng(13);xy=rng.uniform([3,-3],[10,3],(5000,2));ground=np.column_stack((xy,np.zeros(5000),np.ones(5000)))
        obj=np.column_stack((rng.uniform([5,-.5,.4],[6,.5,1.6],(400,3)),np.ones(400)))
        pts=np.vstack((ground,obj)).astype('float32');cal=Calibration(K=[[100,0,100],[0,100,100],[0,0,1]],T_camera_from_lidar=[[0,-1,0,0],[0,0,-1,1.5],[1,0,0,0],[0,0,0,1]],width=200,height=200,reviewed=True,frame_pairing='confirmed')
        return pts,cal
    def test_candidate_requires_ground_supported_cluster(self):
        pts,cal=self.setup_cloud();rows=[{'detection_id':'0','label':'car','target_label':'car','bbox':[80,80,120,128],'status':'unmatched'}]
        result=candidates(pts,rows,cal);self.assertEqual(result[0]['status'],'supported_candidate');self.assertEqual(result[0]['proposal']['status'],'pending')
        self.assertIsNone(candidates(pts[:2],rows,cal)[0]['proposal'])
    def test_add_candidate_endpoint_and_duplicate_preservation(self):
        from api import server
        from core.image_detector_v4 import image_detector
        old=server.store;server.store=SessionStore(Path(tempfile.mkdtemp(prefix='v4-candidate-')))
        try:
            client=TestClient(server.app);pts,cal=self.setup_cloud();s=server.store.create(pts,'candidate');buf=BytesIO();Image.new('RGB',(200,200)).save(buf,format='PNG');s=server.store.add_camera(s['id'],'c.png',buf.getvalue());sid=s['id']
            client.post(f'/api/v4/sessions/{sid}/metadata',json={'units':'metres','axes':'x-forward-y-left-z-up'})
            client.post(f'/api/v4/sessions/{sid}/calibration/0',json=cal.model_dump())
            fake={'model':'fixture','detections':[{'id':'0','label':'car','bbox':[80,80,120,128],'confidence':.8}]}
            with patch.object(image_detector,'infer',return_value=fake):client.post(f'/api/v4/sessions/{sid}/image-detect',json={'revision':s['revision']})
            response=client.post(f'/api/v4/sessions/{sid}/camera-candidate',json={'revision':s['revision'],'camera_index':0,'detection_id':'0','mapping':{'car':'car'}})
            self.assertEqual(response.status_code,200);self.assertEqual(len(response.json()['boxes']),1);self.assertEqual(response.json()['boxes'][0]['status'],'pending')
            stale=client.post(f'/api/v4/sessions/{sid}/camera-candidate',json={'revision':s['revision'],'camera_index':0,'detection_id':'0','mapping':{'car':'car'}});self.assertEqual(stale.status_code,409)
        finally:server.store=old
