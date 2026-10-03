import unittest,tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from fastapi.testclient import TestClient
from core.store import SessionStore
from core.geometry import Cuboid

class V4ConcurrencyTests(unittest.TestCase):
    def test_same_revision_parallel_saves_only_one_wins(self):
        from api import server
        old=server.store;server.store=SessionStore(Path(tempfile.mkdtemp(prefix='v4-concurrency-')))
        try:
            s=server.store.create(np.array([[0,0,0,1]],dtype='float32'),'concurrency')
            with TestClient(server.app) as client:
                def save(i):
                    box=Cuboid(id=str(i),label='car',center=[i,0,0],size=[2,2,2])
                    return client.put('/api/sessions/'+s['id'],json={'revision':0,'boxes':[box.model_dump()]}).status_code
                with ThreadPoolExecutor(max_workers=8) as pool:statuses=list(pool.map(save,range(8)))
            self.assertEqual(statuses.count(200),1);self.assertEqual(statuses.count(409),7);self.assertEqual(server.store.load(s['id'])['revision'],1)
        finally:server.store=old
