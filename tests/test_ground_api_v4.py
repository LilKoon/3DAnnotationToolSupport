import unittest,tempfile
from pathlib import Path
import numpy as np
from fastapi.testclient import TestClient
from core.store import SessionStore

class GroundAPITests(unittest.TestCase):
    def setUp(self):
        from api import server
        self.server=server;self.previous=server.store;server.store=SessionStore(Path(tempfile.mkdtemp(prefix='v4-api-')))
        self.client=TestClient(server.app)
        rng=np.random.default_rng(9);xy=rng.uniform([-5,-5],[5,5],(3000,2));self.points=np.column_stack((xy,np.full(3000,-1.5),np.ones(3000))).astype('float32')
        self.session=server.store.create(self.points,'ground');self.id=self.session['id']
    def tearDown(self):self.server.store=self.previous
    def test_audit_and_ground_cache_preserve_raw(self):
        before=self.server.store.points(self.id).tobytes()
        a=self.client.get(f'/api/v4/sessions/{self.id}/audit');self.assertEqual(a.status_code,200);self.assertFalse(a.json()['units_confirmed'])
        r=self.client.post(f'/api/v4/sessions/{self.id}/ground',json={});self.assertEqual(r.status_code,200)
        self.assertEqual(len(r.json()['display_mask']),len(self.points));self.assertGreater(r.json()['counts']['ground'],2500)
        self.assertEqual(r.json()['cache_key'],self.client.post(f'/api/v4/sessions/{self.id}/ground',json={}).json()['cache_key'])
        self.assertEqual(self.server.store.points(self.id).tobytes(),before)
    def test_metadata_confirmation_and_legacy_revision(self):
        result=self.client.post(f'/api/v4/sessions/{self.id}/metadata',json={'units':'metres','axes':'x-forward-y-left-z-up'})
        self.assertEqual(result.status_code,200);self.assertTrue(self.client.get(f'/api/v4/sessions/{self.id}/audit').json()['units_confirmed'])
        self.assertEqual(self.server.store.load(self.id)['revision'],0)
    def test_invalid_or_missing_session(self):
        self.assertEqual(self.client.post(f'/api/v4/sessions/{self.id}/ground',json={'cell_size':0}).status_code,422)
        self.assertEqual(self.client.get('/api/v4/sessions/'+'f'*32+'/audit').status_code,404)
        self.assertEqual(self.client.get('/api/v4/sessions/bad/audit').status_code,400)
