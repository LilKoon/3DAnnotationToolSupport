from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel,Field,ConfigDict
from core.audit_v4 import audit_input
from core.derived_v4 import ground_record,read_latest,append_record,restore_ground
from core.ground_v4 import ground_contact
from core.geometry import Cuboid

class GroundRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    cell_size:float=Field(default=2.,ge=.5,le=5)
    tolerance:float=Field(default=.08,ge=.02,le=.2)
class MetadataRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    units:Literal['metres','unknown']='unknown'
    axes:Literal['x-forward-y-left-z-up','unknown']='unknown'

def install(app,get_store):
    def session(sid):
        store=get_store()
        try:return store,store.load(sid)
        except FileNotFoundError:raise HTTPException(404,'Session not found')
    @app.get('/api/v4/sessions/{sid}/audit')
    def audit(sid:str):
        store,s=session(sid)
        return audit_input(store.points(sid),s,read_latest(store.root,sid,'metadata'),read_latest(store.root,sid,'calibration'))
    @app.post('/api/v4/sessions/{sid}/metadata')
    def metadata(sid:str,payload:MetadataRequest):
        store,s=session(sid)
        return append_record(store.root,sid,'metadata',payload.model_dump())
    @app.post('/api/v4/sessions/{sid}/ground')
    def ground(sid:str,payload:GroundRequest):
        store,s=session(sid)
        return ground_record(store.root,sid,store.points(sid),payload.cell_size,payload.tolerance)
    @app.get('/api/v4/sessions/{sid}/ground-contact/{box_id}')
    def contact(sid:str,box_id:str):
        store,s=session(sid);box=next((b for b in s['boxes'] if b['id']==box_id),None)
        if box is None:raise HTTPException(404,'Box not found')
        record=ground_record(store.root,sid,store.points(sid))
        result=ground_contact(Cuboid(**box),restore_ground(record))
        units=(read_latest(store.root,sid,'metadata') or {}).get('units')=='metres'
        return {**result,'units_confirmed':units}
