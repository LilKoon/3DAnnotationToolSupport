import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from core.store import SessionStore
from core.geometry import Cuboid

class BoxArchiveTests(unittest.TestCase):
    def test_archive_reload_restore_preserves_every_box_field_and_history(self):
        store=SessionStore(Path(tempfile.mkdtemp(prefix='v3-archive-')))
        s=store.create(np.array([[1,2,0,1]],dtype=np.float32),'Archive test')
        box=Cuboid(id='wrong-box',label='car',center=[1,2,0],size=[4,2,1.5],yaw=.7,axis_signs=[-1,1,-1],status='accepted',source='centerpoint-nuscenes',confidence=.8)
        s=store.update(s['id'],s['revision'],[box])
        archived=store.archive_box(s['id'],s['revision'],box.id)
        self.assertEqual(archived['boxes'],[])
        self.assertEqual(store.load(s['id'])['deleted_boxes'],[box.model_dump()])
        old=store.root/s['id']/f"{s['revision']:08d}.json"
        self.assertEqual(json.loads(old.read_text())['boxes'],[box.model_dump()])
        # Ordinary saves must not discard archived geometry.
        saved=store.update(s['id'],archived['revision'],[])
        restored=store.archive_box(s['id'],saved['revision'],box.id,restore=True)
        self.assertEqual(restored['boxes'],[box.model_dump()])
        self.assertEqual(restored['deleted_boxes'],[])

    def test_stale_or_missing_target_leaves_records_unchanged(self):
        store=SessionStore(Path(tempfile.mkdtemp(prefix='v3-archive-')))
        s=store.create(np.array([[1,2,0,1]],dtype=np.float32),'Archive test')
        with self.assertRaisesRegex(ValueError,'Stale'):store.archive_box(s['id'],10,'missing')
        with self.assertRaisesRegex(ValueError,'không tồn tại'):store.archive_box(s['id'],0,'missing')
        self.assertEqual(store.load(s['id']),s)
