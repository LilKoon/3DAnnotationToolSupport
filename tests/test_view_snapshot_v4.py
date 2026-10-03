import base64,io,tempfile,unittest
from pathlib import Path
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient
from core.store import SessionStore
class ViewSnapshotTests(unittest.TestCase):
    def setUp(self):
        from api import server
        self.server=server;self.old=server.store;server.store=SessionStore(Path(tempfile.mkdtemp(prefix='v4-view-')))
        self.id=server.store.create(np.zeros((2,4),dtype=np.float32),'view')['id'];self.client=TestClient(server.app)
    def tearDown(self):self.server.store=self.old
    def png(self):
        b=io.BytesIO();Image.new('RGB',(20,20),'blue').save(b,format='PNG');return base64.b64encode(b.getvalue()).decode()
    def test_snapshot_is_exclusive_and_does_not_change_annotation(self):
        before=self.server.store.load(self.id);results=[]
        for _ in range(2):
            r=self.client.post(f'/api/v4/sessions/{self.id}/view-snapshot',json={'png':self.png()})
            self.assertEqual(r.status_code,200);results.append(r.json())
            self.assertEqual(self.client.get(r.json()['url']).status_code,200)
        self.assertNotEqual(results[0]['url'],results[1]['url']);self.assertEqual(before,self.server.store.load(self.id))
    def test_invalid_image_rejected(self):
        r=self.client.post(f'/api/v4/sessions/{self.id}/view-snapshot',json={'png':base64.b64encode(b'bad').decode()});self.assertEqual(r.status_code,400)
    def test_unknown_snapshot_and_traversal_rejected(self):
        self.assertEqual(self.client.get(f'/api/v4/sessions/{self.id}/view-snapshots/nope').status_code,404)
