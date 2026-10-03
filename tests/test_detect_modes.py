from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from fastapi.testclient import TestClient
from api import server
from core.geometry import Cuboid
from core.store import SessionStore


class DetectModeTests(unittest.TestCase):
    def setUp(self):
        self.store = SessionStore(Path(tempfile.mkdtemp(prefix='v3-detect-mode-')))
        session = self.store.create(np.array([[0,0,0,1]], dtype=np.float32), 'Modes')
        self.old = Cuboid(id='old', label='car', center=[0,0,0], size=[4,2,1], status='accepted', axis_order=[2,1,0])
        self.session = self.store.update(session['id'], 0, [self.old])
        self.new = Cuboid(id='new', label='car', center=[0,0,0], size=[4,2,1], source='geometry-cpu')

    def run_detection(self, mode, proposals):
        with patch.object(server, 'store', self.store), patch.object(server, 'detect', return_value=proposals), TestClient(server.app) as client:
            return client.post(f"/api/sessions/{self.session['id']}/detect", json={'revision':self.session['revision'], 'model_id':'geometry-cpu', 'mode':mode})

    def test_append_keeps_corrected_box_and_skips_duplicate(self):
        result = self.run_detection('append', [self.new])
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['boxes'], [self.old.model_dump()])
        self.assertEqual(result.json()['detection']['duplicates_skipped'], 1)

    def test_replace_archives_old_and_uses_new_even_when_overlapping(self):
        result = self.run_detection('replace', [self.new])
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual([b['id'] for b in data['boxes']], ['new'])
        self.assertEqual(data['deleted_boxes'], [self.old.model_dump()])
        self.assertEqual(data['detection']['replaced'], 1)
        restored = self.store.archive_box(data['id'], data['revision'], 'old', True)
        self.assertEqual(restored['boxes'][1], self.old.model_dump())

    def test_zero_results_replace_clears_active_boxes_reversibly(self):
        data = self.run_detection('replace', []).json()
        self.assertEqual(data['boxes'], [])
        self.assertEqual(data['deleted_boxes'], [self.old.model_dump()])

    def test_failed_inference_and_invalid_mode_leave_session_unchanged(self):
        self.assertEqual(self.run_detection('invalid', []).status_code, 422)
        with patch.object(server,'store',self.store), patch.object(server,'detect',side_effect=RuntimeError('model failed')), TestClient(server.app) as client:
            response = client.post(f"/api/sessions/{self.session['id']}/detect", json={'revision':self.session['revision'],'model_id':'geometry-cpu','mode':'replace'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.store.load(self.session['id']), self.session)
