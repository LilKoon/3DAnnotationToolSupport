import unittest
from core.geometry import Cuboid
from core.detector_evaluation import score_predictions, aggregate_scores, PROFILES

class EvaluationTests(unittest.TestCase):
    def box(self,id,label='vehicles',x=0):
        return Cuboid(id=id,label=label,center=[x,0,0],size=[4,2,1],status='accepted')
    def test_matching_is_one_to_one_same_label_with_distance_limit(self):
        result=score_predictions([self.box('a'),self.box('b',x=.2),self.box('c','two-wheels')],[self.box('gt')])
        self.assertEqual((result['tp'],result['fp'],result['fn']),(1,2,0))
        self.assertEqual(result['by_label']['two-wheels']['fp'],1)
    def test_aggregate_counts_not_average_of_frame_percentages(self):
        result=aggregate_scores([score_predictions([], [self.box('gt')]),score_predictions([self.box('a')],[self.box('g')])])
        self.assertEqual((result['tp'],result['fp'],result['fn']),(1,0,1))
        self.assertAlmostEqual(result['recall'],.5)
        self.assertEqual(PROFILES['balanced'],.3)

class EvaluationAPITests(unittest.TestCase):
    def test_comparison_preserves_boxes_and_requires_complete_reference(self):
        from pathlib import Path
        from tempfile import mkdtemp
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from core.store import SessionStore
        from api import server
        import numpy as np
        store=SessionStore(Path(mkdtemp(prefix='v3-evaluation-')))
        session=store.create(np.array([[0,0,0,1]],dtype='f4'),'reviewed',['vehicles','two-wheels'])
        gt=Cuboid(id='gt',label='vehicles',center=[0,0,0],size=[4,2,1],status='accepted')
        session=store.update(session['id'],0,[gt])
        def infer(points,model,threshold,path):
            return [Cuboid(id='pred',label='car',center=[0 if model=='centerpoint-nuscenes' else 10,0,0],size=[4,2,1],confidence=.4)]
        with patch.object(server,'store',store),patch.object(server,'detect',side_effect=infer) as run:
            client=TestClient(server.app)
            body={'revision':session['revision'],'session_ids':[session['id']]}
            bad=client.post(f"/api/sessions/{session['id']}/evaluate",json=body)
            self.assertEqual(bad.status_code,400)
            run.assert_not_called()
            result=client.post(f"/api/sessions/{session['id']}/evaluate",json={**body,'confirmed_complete':True})
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(result.json()['recommendation']['model_id'],'centerpoint-nuscenes')
            self.assertEqual(len(result.json()['results']),6)
            self.assertEqual(store.load(session['id']),session)
            self.assertEqual(len(list((store.root/session['id']/'evaluations').glob('*.json'))),1)
            diagnostic=client.get(f"/api/sessions/{session['id']}/input-diagnostics").json()
            self.assertEqual(diagnostic['in_range_fraction']['centerpoint-nuscenes'],1)
            # Profile thresholds override manual thresholds on the API too.
            detection=client.post(f"/api/sessions/{session['id']}/detect",json={'revision':session['revision'],'model_id':'centerpoint-nuscenes','profile':'precise','threshold':.01})
            self.assertEqual(detection.status_code,200,detection.text)
            self.assertEqual(run.call_args.args[2],.55)
            self.assertEqual(detection.json()['detection']['profile'],'precise')
            self.assertEqual(detection.json()['detection']['below_threshold'],1)
    def test_wrong_label_and_far_box_are_missed(self):
        gt=Cuboid(id='gt',label='vehicles',center=[0,0,0],size=[4,2,1])
        far=Cuboid(id='far',label='vehicles',center=[3,0,0],size=[4,2,1])
        result=score_predictions([far],[gt])
        self.assertEqual((result['tp'],result['fp'],result['fn']),(0,1,1))
