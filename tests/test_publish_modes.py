from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from fastapi.testclient import TestClient
from api import server
from core.geometry import Cuboid
from core.store import SessionStore


class PublishModesTests(unittest.TestCase):
    def test_replacement_strips_nested_ids_but_keeps_label_and_attribute_ids(self):
        data={'version':3,'shapes':[{'id':12,'label_id':4,'attributes':[{'spec_id':9,'value':'X,Y,Z'}],'elements':[{'id':13,'label_id':5}]}],'tags':[{'id':14,'label_id':6}]}
        result=server.cvat_replacement_data(data)
        self.assertNotIn('id',result['shapes'][0])
        self.assertNotIn('id',result['shapes'][0]['elements'][0])
        self.assertNotIn('id',result['tags'][0])
        self.assertEqual(result['shapes'][0]['label_id'],4)
        self.assertEqual(result['shapes'][0]['attributes'][0]['spec_id'],9)
        self.assertEqual(data['shapes'][0]['id'],12)

    def test_cvat_error_is_returned_with_actionable_detail(self):
        from cvat_sdk.api_client.exceptions import ApiException
        error=ApiException(status=400,reason='Bad Request')
        error.body='{"shapes":[{"id":["must be absent"]}]}'
        import asyncio
        response=asyncio.run(server.cvat_api_error(None,error))
        self.assertEqual(response.status_code,400)
        self.assertIn(b'must be absent',response.body)

    def test_replace_is_single_write_preserves_other_frames_and_can_repeat(self):
        store=SessionStore(Path(tempfile.mkdtemp(prefix='v3-publish-modes-')))
        session=store.create(np.array([[0,0,0,1]],dtype=np.float32),'Frame',['car'],{'url':'https://cvat.example','job_id':1,'frame':7})
        session=store.update(session['id'],0,[Cuboid(id='new',label='car',center=[0,0,0],size=[4,2,1],status='accepted',axis_order=[1,0,2],axis_signs=[-1,1,1])])
        shape=lambda id,frame:{'id':id,'type':'cuboid','frame':frame,'label_id':1,'points':[0.]*16,'attributes':[],'occluded':False,'outside':False,'z_order':0}
        class Job:
            data={'version':1,'shapes':[shape(10,7),shape(11,7),shape(12,8)],'tracks':[],'tags':[]}
            calls=[]
            def get_labels(self):return [SimpleNamespace(name='car',id=1,attributes=[])]
            def get_annotations(self):return SimpleNamespace(to_dict=lambda:self.data)
            def set_annotations(self,data):
                self.assert_no_ids(data.to_dict())
                self.calls.append(data);self.data=data.to_dict();self.data['version']+=1
                for i,item in enumerate(self.data['shapes']):item.setdefault('id',100+i)
            def assert_no_ids(self,data):
                if isinstance(data,dict):
                    assert 'id' not in data, 'CVAT PUT rejects annotation IDs'
                    for value in data.values():self.assert_no_ids(value)
                elif isinstance(data,list):
                    for value in data:self.assert_no_ids(value)
        job=Job()
        credentials={'url':'https://cvat.example','job_id':1,'username':'test','password':'test'}
        with patch.object(server,'store',store),patch.object(server.Credentials,'connect',return_value=(None,job)),TestClient(server.app) as client:
            path=f"/api/sessions/{session['id']}"
            preview=client.post(path+'/publish-preview',json=credentials).json()
            self.assertEqual([t['id'] for t in preview['targets']],[10,11])
            payload={**credentials,'confirm':True,'mode':'replace','revision':preview['revision'],'replacement_token':preview['replacement_token']}
            result=client.post(path+'/publish',json=payload)
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(result.json()['replaced'],2)
            self.assertEqual(len(job.calls),1)
            self.assertEqual([s['frame'] for s in job.data['shapes']],[8,7])
            self.assertAlmostEqual(job.data['shapes'][1]['points'][5],-np.pi/2)
            self.assertEqual(job.data['shapes'][1]['points'][6:9],[2,4,1])
            self.assertEqual(job.data['shapes'][0]['label_id'],1)
            self.assertEqual(job.data['shapes'][0]['points'],[0.]*16)
            self.assertTrue(Path(result.json()['backup']).is_file())
            self.assertEqual(client.post(path+'/publish',json=payload).status_code,409)
            preview=client.post(path+'/publish-preview',json=credentials).json()
            payload.update(revision=preview['revision'],replacement_token=preview['replacement_token'])
            self.assertEqual(client.post(path+'/publish',json=payload).json()['published'],1)
            self.assertEqual(len(job.data['shapes']),2)
            preview=client.post(path+'/publish-preview',json=credentials).json()
            payload.update(revision=preview['revision'],replacement_token=preview['replacement_token'])
            job.data['version']+=1
            self.assertEqual(client.post(path+'/publish',json=payload).status_code,409)
            self.assertEqual(len(job.calls),2)
            job.data['tracks']=[{'id':99}]
            self.assertEqual(client.post(path+'/publish-preview',json=credentials).status_code,400)
