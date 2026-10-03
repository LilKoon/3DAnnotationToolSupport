import unittest,tempfile
from pathlib import Path
from io import BytesIO
from unittest.mock import patch
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient
from core.store import SessionStore
from core.geometry import Cuboid

class AssistAPITests(unittest.TestCase):
    def setUp(self):
        from api import server
        self.server=server;self.previous=server.store;server.store=SessionStore(Path(tempfile.mkdtemp(prefix='v4-camera-api-')));self.client=TestClient(server.app)
        pts=np.array([[x,y,z,1] for x in [-.5,0,.5] for y in [-.5,0,.5] for z in [9.5,10,10.5]],dtype='float32')
        s=server.store.create(pts,'camera');box=Cuboid(id='a',label='car',center=[0,0,10],size=[2,2,2],status='accepted');s=server.store.update(s['id'],0,[box]);buf=BytesIO();Image.new('RGB',(200,200)).save(buf,format='PNG');self.s=server.store.add_camera(s['id'],'front.png',buf.getvalue());self.id=s['id']
        self.cal={'K':[[100,0,100],[0,100,100],[0,0,1]],'T_camera_from_lidar':np.eye(4).tolist(),'width':200,'height':200,'reviewed':True,'frame_pairing':'confirmed'}
    def tearDown(self):self.server.store=self.previous
    def test_calibration_size_validation_and_projection(self):
        bad={**self.cal,'width':300};self.assertEqual(self.client.post(f'/api/v4/sessions/{self.id}/calibration/0',json=bad).status_code,400)
        self.assertEqual(self.client.post(f'/api/v4/sessions/{self.id}/calibration/0',json=self.cal).status_code,200)
        result=self.client.get(f'/api/v4/sessions/{self.id}/projection/0');self.assertEqual(result.status_code,200);self.assertEqual(result.json()['boxes'][0]['box_id'],'a')
    def test_reference_only_missing_calibration(self):
        response=self.client.get(f'/api/v4/sessions/{self.id}/projection/0');self.assertEqual(response.status_code,200);self.assertFalse(response.json()['ready'])
    def test_image_detection_does_not_edit_boxes_and_matching_requires_units(self):
        from core.image_detector_v4 import image_detector
        before=self.server.store.load(self.id)
        fake={'model':'test','detections':[{'id':'0','label':'car','bbox':[88,88,112,112],'confidence':.8}]}
        with patch.object(image_detector,'infer',return_value=fake):
            result=self.client.post(f'/api/v4/sessions/{self.id}/image-detect',json={'revision':self.s['revision']});self.assertEqual(result.status_code,200)
        self.assertEqual(self.server.store.load(self.id),before)
        self.client.post(f'/api/v4/sessions/{self.id}/calibration/0',json=self.cal)
        response=self.client.post(f'/api/v4/sessions/{self.id}/evidence',json={'mapping':{'car':'car'}});self.assertFalse(response.json()['ready'])
        self.client.post(f'/api/v4/sessions/{self.id}/metadata',json={'units':'metres','axes':'x-forward-y-left-z-up'})
        response=self.client.post(f'/api/v4/sessions/{self.id}/evidence',json={'mapping':{'car':'car'}});self.assertTrue(response.json()['ready']);self.assertEqual(response.json()['cameras']['0'][0]['status'],'matched')
        self.assertEqual(self.server.store.load(self.id),before)
    def test_stale_revision_and_unknown_mapping(self):
        self.assertEqual(self.client.post(f'/api/v4/sessions/{self.id}/image-detect',json={'revision':999}).status_code,409)
        self.assertEqual(self.client.post(f'/api/v4/sessions/{self.id}/evidence',json={'mapping':{'car':'made-up'}}).status_code,400)
