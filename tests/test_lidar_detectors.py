import ast
import base64
from io import BytesIO
import json
import math
from pathlib import Path
from tempfile import mkdtemp
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import httpx
import numpy as np
from fastapi.testclient import TestClient

from core.detector_service import DetectorService
from core.geometry import Cuboid
from core.lidar_presets import GUIDELINE_LABELS, NUSCENES_CLASSES, PRESETS, PROTOCOL, COORDINATES, model_points, validate_label_map
from core.proposal_review import cuboid_iou, merge_proposals
from core.store import SessionStore
from gpu_worker.server import create_app


def contract(**extra):
    return {"protocol": PROTOCOL, "coordinate_system": COORDINATES, "classes": GUIDELINE_LABELS, **extra}


class FakeRuntime:
    def __init__(self):
        self.calls = []

    def status(self):
        return [{"id": key, "classes": NUSCENES_CLASSES, "ready": True, "reason": "Test fixture"} for key in PRESETS]

    def infer(self, points, model_id, threshold, intensity_scale):
        self.calls.append((points.copy(), model_id, threshold, intensity_scale))
        return [{"label": label, "center": [i*8., 0., 0.], "size": [4., 2., 2.], "yaw": .4, "confidence": .9} for i, label in enumerate(NUSCENES_CLASSES)]


class PresetTests(unittest.TestCase):
    def test_single_sweep_features_and_intensity_are_preserved(self):
        points = np.array([[2, 3, -1, 31], [5, 6, 0, 127]], dtype=np.float32)
        np.testing.assert_array_equal(model_points(points, 'pointpillars-nuscenes'), points)
        cp = model_points(points, 'centerpoint-nuscenes')
        np.testing.assert_array_equal(cp[:, :4], points)
        np.testing.assert_array_equal(cp[:, 4], [0, 0])
        np.testing.assert_array_equal(model_points(points, 'centerpoint-nuscenes', 2)[:, 3], points[:, 3]*2)
        self.assertEqual(set(GUIDELINE_LABELS), set(NUSCENES_CLASSES))
        self.assertNotEqual(GUIDELINE_LABELS, NUSCENES_CLASSES)

    def test_bad_cloud_and_wrong_taxonomy_mapping_rejected(self):
        for data in [np.ones((1, 5)), np.full((1, 4), np.nan), np.empty((0, 4)), np.array([[1000, 1000, 1000, 1]])]:
            with self.assertRaises(ValueError):
                model_points(data, 'pointpillars-nuscenes')
        validate_label_map({'car':'Car','truck':'__skip__'}, ['Car'])
        with self.assertRaises(ValueError):
            validate_label_map({'truck':'missing-job-label'}, GUIDELINE_LABELS)
        with self.assertRaises(ValueError):
            validate_label_map({'Cyclist':'bicycle'}, GUIDELINE_LABELS)

    def test_rotated_3d_iou_and_review_preservation(self):
        box = Cuboid(id='edited', label='truck', center=[0, 0, 0], size=[4, 2, 2], yaw=math.pi/4, status='accepted', source='pointpillars-nuscenes', axis_signs=[-1, 1, -1])
        near = box.model_copy(update={'id':'new','center':[.1,0,0], 'label':'car','status':'pending'})
        self.assertGreater(cuboid_iou(box, near), .8)
        far = box.model_copy(update={'id':'far', 'center':[20,0,0]})
        merged, skipped = merge_proposals([box], [near, far])
        self.assertEqual(skipped, 1)
        self.assertEqual([item.id for item in merged], ['edited', 'far'])
        self.assertEqual(merged[0].model_dump(), box.model_dump())
        perpendicular = box.model_copy(update={'yaw':box.yaw+math.pi/2})
        self.assertAlmostEqual(cuboid_iou(box, perpendicular), 1/3)
        self.assertEqual(cuboid_iou(box, box.model_copy(update={'center':[0,0,10]})), 0)


class RemoteTests(unittest.TestCase):
    def setUp(self):
        self.service = DetectorService(Path(mkdtemp(prefix='v3-settings-test-')))
        self.service.configure('remote', 'https://gpu.example.com', 'test-secret', 1)
        self.runtime = FakeRuntime()
        self.worker = TestClient(create_app(self.runtime, token='test-secret'))

    def remote_get(self, url, **kwargs):
        return self.worker.get('/health', headers=kwargs['headers'])

    def remote_post(self, url, **kwargs):
        return self.worker.post('/infer/' + url.rsplit('/',1)[-1], params=kwargs['params'], content=kwargs['content'], headers=kwargs['headers'])

    def test_both_models_roundtrip_all_ten_classes_and_editable_geometry(self):
        points = np.array([[1,2,-1,99]], dtype=np.float32)
        with patch('core.detector_service.httpx.get', side_effect=self.remote_get), patch('core.detector_service.httpx.post', side_effect=self.remote_post):
            self.assertTrue(all(item['ready'] for item in self.service.catalog()))
            for model in PRESETS:
                boxes = self.service.infer(points, model, .3)
                self.assertEqual([box.label for box in boxes], NUSCENES_CLASSES)
                self.assertEqual(boxes[0].center, [0,0,0])
                self.assertEqual(boxes[0].size, [4,2,2])
                self.assertEqual(boxes[0].yaw, .4)
                self.assertTrue(all(box.status=='pending' and box.source==model and box.axis_signs==[1,1,1] for box in boxes))
        np.testing.assert_array_equal(self.runtime.calls[0][0], points)
        self.assertEqual(self.runtime.calls[1][1], 'centerpoint-nuscenes')

    def test_auth_wrong_contract_and_http_failure_are_not_ready(self):
        self.assertEqual(self.worker.get('/health').status_code, 401)
        self.assertEqual(self.worker.post('/infer/pointpillars-nuscenes', content=b'').status_code, 401)
        bad = httpx.Response(200, json=contract(coordinate_system='camera'), request=httpx.Request('GET','https://gpu.example.com/health'))
        with patch('core.detector_service.httpx.get', return_value=bad):
            self.assertFalse(any(item['ready'] for item in self.service.catalog(force=True)))
        unauthorized = httpx.Response(401, json={'detail':'bad token'}, request=httpx.Request('GET','https://gpu.example.com/health'))
        with patch('core.detector_service.httpx.get', return_value=unauthorized):
            models = self.service.catalog(force=True)
        self.assertFalse(any(item['ready'] for item in models))
        self.assertIn('401', models[0]['reason'])

    def test_invalid_prediction_rejected_and_threshold_enforced(self):
        sample={'label':'car','center':[1,2,3],'size':[4,2,2],'yaw':0,'confidence':.9}
        with patch('core.detector_service.httpx.get', side_effect=self.remote_get):
            for wrong in [dict(sample,label='rider'), dict(sample,size=[-1,2,2]), dict(sample,confidence=2), dict(sample,yaw=float('inf'))]:
                reply=httpx.Response(200,content=json.dumps(contract(model_id='pointpillars-nuscenes',boxes=[wrong])).encode(), request=httpx.Request('POST','https://gpu.example.com/infer/pointpillars-nuscenes'))
                with patch('core.detector_service.httpx.post', return_value=reply), self.assertRaises(RuntimeError):
                    self.service.infer(np.array([[1,2,0,1]],dtype=np.float32), 'pointpillars-nuscenes', 0)
            reply=httpx.Response(200,json=contract(model_id='pointpillars-nuscenes',boxes=[dict(sample,confidence=.2)]),request=httpx.Request('POST','https://gpu.example.com/infer/pointpillars-nuscenes'))
            with patch('core.detector_service.httpx.post',return_value=reply):
                self.assertEqual(self.service.infer(np.array([[1,2,0,1]],dtype=np.float32), 'pointpillars-nuscenes', .3), [])

    def test_settings_are_append_only_and_never_return_token(self):
        self.service.configure('remote','https://gpu.example.com',None,2)
        self.assertEqual(len(list(self.service.settings_root.glob('*.json'))),2)
        self.assertEqual(self.service.settings()['api_token'],'test-secret')
        self.assertNotIn('api_token',self.service.public_settings())
        with self.assertRaises(ValueError):
            self.service.configure('remote','https://different.example.com',None,1)


class ApiIntegrationTests(unittest.TestCase):
    def test_default_labels_rerun_edit_and_failure_preserve_session(self):
        from api import server
        store=SessionStore(Path(mkdtemp(prefix='v3-detector-api-')))
        with patch.object(server,'store',store):
            client=TestClient(server.app)
            session=client.post('/api/sessions/upload?filename=a.bin',content=np.array([[1,2,0,1]],dtype='<f4').tobytes()).json()
            self.assertEqual(session['labels'],GUIDELINE_LABELS)
            proposal=Cuboid(id='first',label='car',center=[1,2,0],size=[4,2,2],source='pointpillars-nuscenes')
            with patch.object(server,'detect',return_value=[proposal]):
                response=client.post(f"/api/sessions/{session['id']}/detect",json={'revision':0,'model_id':'pointpillars-nuscenes'})
            self.assertEqual(response.status_code,200,response.text)
            saved=response.json()
            saved['boxes'][0].update(center=[1.1,2,0],axis_signs=[-1,1,-1],status='accepted')
            edited=client.put(f"/api/sessions/{session['id']}",json={'revision':saved['revision'],'boxes':saved['boxes']}).json()
            with patch.object(server,'detect',return_value=[proposal.model_copy(update={'id':'second'})]):
                rerun=client.post(f"/api/sessions/{session['id']}/detect",json={'revision':edited['revision'],'model_id':'pointpillars-nuscenes'}).json()
            self.assertEqual(rerun['boxes'],edited['boxes'])
            self.assertEqual(rerun['detection']['duplicates_skipped'],1)
            with patch.object(server,'detect',side_effect=RuntimeError('GPU offline')):
                failed=client.post(f"/api/sessions/{session['id']}/detect",json={'revision':rerun['revision'],'model_id':'pointpillars-nuscenes'})
            self.assertEqual(failed.status_code,400)
            self.assertEqual(store.load(session['id'])['revision'],rerun['revision'])
            self.assertEqual(store.load(session['id'])['boxes'],edited['boxes'])

    def test_wrong_label_map_is_rejected_before_model_runs(self):
        from api import server
        store=SessionStore(Path(mkdtemp(prefix='v3-label-test-')))
        session=store.create(np.array([[1,2,0,1]],dtype=np.float32),'frame')
        with patch.object(server,'store',store), patch.object(server,'detect') as run:
            response=TestClient(server.app).post(f"/api/sessions/{session['id']}/detect",json={'revision':0,'model_id':'centerpoint-nuscenes','label_map':{'trailer':'missing-job-label'}})
            self.assertEqual(response.status_code,400)
            run.assert_not_called()

    def test_downloads_contain_no_user_data_and_notebook_cells_parse(self):
        from api import server
        client=TestClient(server.app)
        bundle=client.get('/api/detector/bundle')
        self.assertEqual(bundle.status_code,200)
        with ZipFile(BytesIO(bundle.content)) as archive:
            self.assertIn('v3/gpu_worker/verify.py',archive.namelist())
            self.assertFalse(any('/data/' in name for name in archive.namelist()))
        notebook=client.get('/api/detector/colab')
        self.assertEqual(notebook.status_code,200)
        data=json.loads(notebook.content)
        for index, cell in enumerate(data['cells']):
            if cell['cell_type']=='code':
                ast.parse(''.join(cell['source']),filename=f'cell-{index}')
        bootstrap=ast.parse(''.join(data['cells'][1]['source']))
        payload=next(node.value.value for node in bootstrap.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PAYLOAD' for t in node.targets))
        with ZipFile(BytesIO(base64.b64decode(payload))) as archive:
            self.assertEqual(archive.read('v3/core/lidar_runtime.py'),(Path(__file__).resolve().parents[1]/'core/lidar_runtime.py').read_bytes())


if __name__=='__main__':
    unittest.main()
