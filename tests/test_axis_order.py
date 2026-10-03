from itertools import permutations
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from pydantic import ValidationError
from fastapi.testclient import TestClient
from api import server
from core.geometry import AxisConvention, Cuboid, cvat_points, axis_attributes, parse_cvat_points
from core.store import SessionStore


class AxisOrderTests(unittest.TestCase):
    def test_all_six_orders_roundtrip_cvat_attributes_without_geometry_changes(self):
        for order in permutations([0,1,2]):
            box=Cuboid(id='box',label='car',center=[1,2,3],size=[4,2,1.5],yaw=.8,axis_order=order,axis_signs=[-1,1,-1])
            plain=Cuboid(**{**box.model_dump(),'axis_order':[0,1,2],'axis_signs':[1,1,1]})
            self.assertEqual(cvat_points(box),cvat_points(plain))
            restored=parse_cvat_points('restored','car',cvat_points(box),0,axis_attributes(box))
            self.assertEqual(restored.axis_order,list(order))
            self.assertEqual(restored.axis_signs,box.axis_signs)
            self.assertEqual(restored.center,box.center)
            self.assertEqual(restored.size,box.size)
            self.assertEqual(restored.yaw,box.yaw)

    def test_duplicate_missing_or_invalid_axes_rejected_and_old_boxes_supported(self):
        for order in [[0,0,2],[0,1],[0,1,3]]:
            with self.assertRaises(ValidationError):AxisConvention(axis_order=order)
        old=Cuboid(id='old',label='car',center=[0,0,0],size=[4,2,1])
        self.assertEqual(old.axis_order,[0,1,2])

    def test_default_scope_bulk_scope_and_archived_boxes_preserved(self):
        store=SessionStore(Path(tempfile.mkdtemp(prefix='v3-axis-order-')))
        session=store.create(np.array([[0,0,0,1]],dtype=np.float32),'Axis test')
        box=Cuboid(id='a',label='car',center=[1,2,3],size=[4,2,1],yaw=.7)
        session=store.update(session['id'],0,[box])
        convention=AxisConvention(axis_order=[2,0,1],axis_signs=[1,-1,1])
        session=store.set_axis_convention(session['id'],session['revision'],convention)
        self.assertEqual(session['boxes'],[box.model_dump()])
        self.assertEqual(store.load(session['id'])['axis_convention'],convention.model_dump())
        session=store.set_axis_convention(session['id'],session['revision'],convention,True)
        for field in ['center','size','yaw','status','source']:
            self.assertEqual(session['boxes'][0][field],box.model_dump()[field])
        self.assertEqual(session['boxes'][0]['axis_order'],[2,0,1])
        archived=store.archive_box(session['id'],session['revision'],'a')
        updated=store.set_axis_convention(session['id'],archived['revision'],AxisConvention(),True)
        self.assertEqual(updated['deleted_boxes'],archived['deleted_boxes'])

    def test_api_default_applies_to_new_detections_existing_order_survives(self):
        store=SessionStore(Path(tempfile.mkdtemp(prefix='v3-axis-api-')))
        session=store.create(np.array([[1,2,0,10]],dtype=np.float32),'Axis test')
        old=Cuboid(id='old',label='car',center=[10,2,0],size=[4,2,1],axis_order=[1,0,2])
        session=store.update(session['id'],0,[old])
        with patch.object(server,'store',store),TestClient(server.app) as client:
            path=f"/api/sessions/{session['id']}/axis-convention"
            invalid=client.post(path,json={'revision':session['revision'],'convention':{'axis_order':[0,0,2]}})
            self.assertEqual(invalid.status_code,422)
            payload={'revision':session['revision'],'convention':{'axis_order':[2,1,0],'axis_signs':[-1,1,1]}}
            response=client.post(path,json=payload);self.assertEqual(response.status_code,200)
            self.assertEqual(client.post(path,json=payload).status_code,409)
            current=response.json()
            proposal=Cuboid(id='new',label='car',center=[1,2,0],size=[4,2,1])
            with patch.object(server,'detect',return_value=[proposal]):
                result=client.post(f"/api/sessions/{session['id']}/detect",json={'revision':current['revision'],'model_id':'geometry-cpu','threshold':.3})
            self.assertEqual(result.status_code,200)
            boxes=result.json()['boxes']
            self.assertEqual(boxes[0]['axis_order'],[1,0,2])
            self.assertEqual(boxes[1]['axis_order'],[2,1,0])
            self.assertEqual(boxes[1]['axis_signs'],[-1,1,1])
