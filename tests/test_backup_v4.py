import unittest,tempfile
from pathlib import Path
import numpy as np
from fastapi.testclient import TestClient
from core.store import SessionStore
from core.geometry import Cuboid
from core.derived_v4 import read_latest

class BackupV4Tests(unittest.TestCase):
    def setUp(self):
        from api import server
        self.server=server;self.previous=server.store;server.store=SessionStore(Path(tempfile.mkdtemp(prefix='v4-backup-')));self.client=TestClient(server.app)
        s=server.store.create(np.array([[1,2,3,1],[4,5,6,1]],dtype='float32'),'backup');self.s=server.store.update(s['id'],0,[Cuboid(id='a',label='car',center=[2,2,2],size=[2,2,2])]);self.id=s['id']
    def tearDown(self):self.server.store=self.previous
    def test_backup_restore_forks_and_preserves_source(self):
        self.client.post(f'/api/v4/sessions/{self.id}/metadata',json={'units':'metres','axes':'x-forward-y-left-z-up'})
        before=self.server.store.load(self.id);backup=self.client.get(f'/api/v4/sessions/{self.id}/review-backup');self.assertEqual(backup.status_code,200)
        result=self.client.post(f'/api/v4/sessions/{self.id}/restore-review',json=backup.json());self.assertEqual(result.status_code,200);new=result.json()
        self.assertNotEqual(new['id'],self.id);self.assertEqual(new['boxes'],before['boxes']);self.assertEqual(self.server.store.load(self.id),before);self.assertEqual(read_latest(self.server.store.root,new['id'],'metadata')['units'],'metres')
    def test_wrong_point_cloud_rejected(self):
        backup=self.client.get(f'/api/v4/sessions/{self.id}/review-backup').json();backup['point_fingerprint']='bad'
        self.assertEqual(self.client.post(f'/api/v4/sessions/{self.id}/restore-review',json=backup).status_code,400)
    def test_comparison_requires_independent_reference(self):
        payload={'predictions':self.s['boxes'],'truth':self.s['boxes'],'confirmed_complete':False}
        self.assertEqual(self.client.post(f'/api/v4/sessions/{self.id}/compare-annotations',json=payload).status_code,400)
        payload['confirmed_complete']=True;result=self.client.post(f'/api/v4/sessions/{self.id}/compare-annotations',json=payload)
        self.assertEqual(result.status_code,200);self.assertEqual(result.json()['tp'],1)
