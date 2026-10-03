from fastapi import HTTPException,Response
from pydantic import BaseModel,Field,ConfigDict
from core.geometry import Cuboid
from core.evaluation_v4 import compare_annotations,quality_report
from core.derived_v4 import append_record

class ComparisonRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    predictions:list[Cuboid]=Field(max_length=2000)
    truth:list[Cuboid]=Field(max_length=2000)
    confirmed_complete:bool=False
    distance_limit:float=Field(default=2.,gt=0,le=10)

def install(app,get_store):
    def session(sid):
        store=get_store()
        try:return store,store.load(sid)
        except FileNotFoundError:raise HTTPException(404,'Session not found')
    @app.get('/favicon.ico',include_in_schema=False)
    def favicon():return Response(status_code=204)
    @app.get('/api/v4/sessions/{sid}/quality')
    def quality(sid:str):
        store,s=session(sid);return quality_report([Cuboid(**b) for b in s['boxes'] if b['status']!='rejected'])
    @app.post('/api/v4/sessions/{sid}/compare-annotations')
    def compare(sid:str,payload:ComparisonRequest):
        store,s=session(sid)
        if not payload.confirmed_complete:raise ValueError('Confirm independent complete ground truth before comparison')
        return append_record(store.root,sid,'assistance-evaluations',compare_annotations(payload.predictions,payload.truth,payload.distance_limit))
