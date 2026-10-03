import unittest
from core.lidar_presets import validate_label_map

class JobLabelMappingTests(unittest.TestCase):
    def test_grouped_job_names_are_allowed(self):
        validate_label_map({'car':'vehicles','motorcycle':'two-wheels','bicycle':'two-wheels'}, ['vehicles','two-wheels'])
    def test_unknown_target_rejected(self):
        with self.assertRaises(ValueError):
            validate_label_map({'car':'vehicle'}, ['vehicles'])
    def test_unknown_model_class_rejected(self):
        with self.assertRaises(ValueError):
            validate_label_map({'animal':'Animal'}, ['Animal'])

class ProposalFilteringTests(unittest.TestCase):
    def test_defaults_and_filter_reasons(self):
        from core.label_mapping import default_mapping, filter_proposals
        from core.geometry import Cuboid
        mapping=default_mapping(['vehicles','two-wheels','pedestrian','Animal','Obstacle'])
        self.assertEqual(mapping['car'],'vehicles')
        self.assertEqual(mapping['bicycle'],'two-wheels')
        self.assertEqual(mapping['truck'],'__skip__')
        self.assertNotIn('Animal',mapping.values())
        proposals=[Cuboid(id=str(i),label=label,center=[i*10,0,0],size=[2,1,1],confidence=score) for i,(label,score) in enumerate([('car',.7),('motorcycle',.2),('bicycle',.1),('truck',.8),('unknown',.8)])]
        boxes,report=filter_proposals(proposals,mapping,.3,{'motorcycle':.15})
        self.assertEqual([box.label for box in boxes],['vehicles','two-wheels'])
        self.assertEqual(report['below_threshold'],1)
        self.assertEqual(report['explicit_skip'],1)
        self.assertEqual(report['unmapped'],1)
        self.assertEqual(proposals[0].label,'car')

    def test_api_grouped_labels_and_per_class_threshold_persist(self):
        import numpy as np
        from pathlib import Path
        from tempfile import mkdtemp
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from api import server
        from core.store import SessionStore
        from core.geometry import Cuboid
        store=SessionStore(Path(mkdtemp(prefix='v3-grouped-api-')))
        session=store.create(np.array([[1,2,0,1]],dtype=np.float32),'frame',['vehicles','two-wheels','Animal'])
        proposals=[Cuboid(id=str(i),label=label,center=[i*10,0,0],size=[2,1,1],confidence=score) for i,(label,score) in enumerate([('car',.7),('motorcycle',.2),('bicycle',.1)])]
        with patch.object(server,'store',store), patch.object(server,'detect',return_value=proposals) as run:
            result=TestClient(server.app).post(f"/api/sessions/{session['id']}/detect",json={'revision':0,'model_id':'pointpillars-nuscenes','class_thresholds':{'motorcycle':.15}})
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(run.call_args.args[2],.15)
            self.assertEqual([box['label'] for box in result.json()['boxes']],['vehicles','two-wheels'])
            self.assertEqual(store.load(session['id'])['detection']['below_threshold'],1)
            before=store.load(session['id'])['revision']
            bad=TestClient(server.app).post(f"/api/sessions/{session['id']}/detect",json={'revision':before,'model_id':'pointpillars-nuscenes','class_thresholds':{'car':2}})
            self.assertEqual(bad.status_code,400)
            self.assertEqual(store.load(session['id'])['revision'],before)

class CVATLabelImportTests(unittest.TestCase):
    def test_import_keeps_job_label_ids_colors_and_reports_bad_box(self):
        from types import SimpleNamespace as NS
        from io import BytesIO
        from pathlib import Path
        from tempfile import mkdtemp
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from api import server
        from core.store import SessionStore
        from core.geometry import Cuboid,cvat_points
        store=SessionStore(Path(mkdtemp(prefix='v3-label-import-')))
        labels=[NS(id=10,name='vehicles',color='#ff0000',attributes=[]),NS(id=11,name='two-wheels',color='#00ff00',attributes=[]),NS(id=12,name='Animal',color='#ffaa00',attributes=[])]
        valid=cvat_points(Cuboid(id='a',label='vehicles',center=[1,2,0],size=[4,2,1]))
        shapes=[NS(id=1,frame=0,type=NS(value='cuboid'),label_id=10,attributes=[],points=valid),NS(id=2,frame=0,type=NS(value='cuboid'),label_id=11,attributes=[],points=[])]
        pcd=b'VERSION .7\nFIELDS x y z intensity\nSIZE 4 4 4 4\nTYPE F F F F\nCOUNT 1 1 1 1\nWIDTH 1\nHEIGHT 1\nPOINTS 1\nDATA ascii\n1 2 0 1\n'
        job=NS(start_frame=0,get_frames_info=lambda:[NS(name='a.pcd')],get_frame=lambda *args,**kwargs:BytesIO(pcd),get_labels=lambda:labels,get_annotations=lambda:NS(shapes=shapes,tracks=[]))
        with patch.object(server,'store',store),patch.object(server.Credentials,'connect',return_value=(None,job)):
            response=TestClient(server.app).post('/api/sessions/cvat',json={'url':'https://example.test','username':'test','password':'test','job_id':1,'frame':0})
        self.assertEqual(response.status_code,200,response.text)
        data=response.json()
        self.assertEqual(data['labels'],['vehicles','two-wheels','Animal'])
        self.assertEqual(data['label_specs'][0],{'id':10,'name':'vehicles','color':'#ff0000'})
        self.assertEqual(len(data['boxes']),1)
        self.assertEqual(len(data['import_warnings']),1)
        self.assertIn('2',data['import_warnings'][0])
