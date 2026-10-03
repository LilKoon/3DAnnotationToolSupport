from __future__ import annotations
import hashlib,json
from uuid import uuid4
from fastapi import HTTPException
from pydantic import BaseModel,Field,ConfigDict
from PIL import Image
from core.geometry import Cuboid
from core.camera_v4 import Calibration,project_points,project_box,associate
from core.image_detector_v4 import image_detector
from core.derived_v4 import read_latest,append_record,fingerprint
from core.audit_v4 import audit_input
from core.candidates_v4 import candidates
from core.measurements_v4 import measure
from core.proposal_review import merge_proposals
from core.topology_v4 import associate_by_topology

class ImageRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision:int=Field(ge=0)
    threshold:float=Field(default=.25,ge=0,le=1)
class EvidenceRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    mapping:dict[str,str]=Field(default_factory=dict)
    topology:dict[str,str]=Field(default_factory=dict)
class CandidateRequest(EvidenceRequest):
    revision:int=Field(ge=0)
    camera_index:int=Field(ge=0,le=7)
    detection_id:str=Field(max_length=100)

def install(app,get_store):
    def session(sid):
        store=get_store()
        try:return store,store.load(sid)
        except FileNotFoundError:raise HTTPException(404,'Session not found')
    def camera(store,sid,index):
        try:return store.camera_path(sid,index)
        except (IndexError,FileNotFoundError):raise HTTPException(404,'Camera not found')
    def checked_mapping(s,mapping):
        if len(mapping)>200 or any(target not in s['labels'] and target!='__skip__' for target in mapping.values()):raise ValueError('Mapping target must exist in session labels')
        return {key:target for key,target in mapping.items() if target!='__skip__'}
    def evidence_data(store,s,mapping,topology):
        sid=s['id'];mapping=checked_mapping(s,mapping);calibrations=read_latest(store.root,sid,'calibration') or {};detected=read_latest(store.root,sid,'image-detections') or {};points=store.points(sid)
        audit=audit_input(points,s,read_latest(store.root,sid,'metadata'),calibrations);rows={};proposals={}
        index_to_fov = {v: k for k, v in topology.items() if v}
        for c in s['cameras']:
            index=str(c['index']);record=detected.get('cameras',{}).get(index,{})
            if record.get('image_sha256')!=hashlib.sha256(camera(store,sid,c['index']).read_bytes()).hexdigest():continue
            cal=Calibration(**calibrations[index]) if index in calibrations else None
            detections=record.get('detections',[])
            if cal is not None:
                if not audit['units_confirmed']:cal.reviewed=False
                rows[index]=associate([Cuboid(**b) for b in s['boxes']],detections,cal,mapping,points)
                for row in rows[index]:row['target_label']=mapping.get(row['label'])
                if cal.reviewed and cal.frame_pairing=='confirmed':proposals[index]=candidates(points,rows[index],cal)
            elif index in index_to_fov:
                rows[index]=associate_by_topology([Cuboid(**b) for b in s['boxes']],detections,mapping,index_to_fov[index])
            else:rows[index]=[{'detection_id':d['id'],'label':d['label'],'bbox':d['bbox'],'box_id':None,'status':'reference_only'} for d in detections]
        return {'ready':audit['fusion_ready'],'cameras':rows,'candidates':proposals,'revision':s['revision'],'calibration_version':hashlib.sha256(json.dumps(calibrations,sort_keys=True).encode()).hexdigest(),'warnings':['Evidence is geometry support, not a recalibrated detector confidence. Camera-only objects remain review items.']}
    @app.get('/api/v4/image-detector')
    def image_status():return image_detector.status()
    @app.get('/api/v4/sessions/{sid}/calibration')
    def calibrations(sid:str):
        store,s=session(sid);return read_latest(store.root,sid,'calibration') or {}
    @app.post('/api/v4/sessions/{sid}/calibration/{index}')
    def set_calibration(sid:str,index:int,payload:Calibration):
        store,s=session(sid);path=camera(store,sid,index)
        with Image.open(path) as img:
            if img.size!=(payload.width,payload.height):raise ValueError('Calibration dimensions must match original camera image; adapt intrinsics for crop/resize first')
        cal=read_latest(store.root,sid,'calibration') or {};cal[str(index)]=payload.model_dump()
        return append_record(store.root,sid,'calibration',cal)
    @app.get('/api/v4/sessions/{sid}/projection/{index}')
    def projection(sid:str,index:int):
        store,s=session(sid);camera(store,sid,index);calibrations=read_latest(store.root,sid,'calibration') or {}
        if str(index) not in calibrations:return {'ready':False,'reason':'Chưa có calibration; ảnh tham khảo','boxes':[],'points':[]}
        cal=Calibration(**calibrations[str(index)]);points=store.points(sid);points=points[::max(1,int(len(points)//4000+1))]
        uv,depth,valid=project_points(points,cal);boxes=[p for b in s['boxes'] if (p:=project_box(Cuboid(**b),cal)) is not None]
        return {'ready':True,'reviewed':cal.reviewed,'frame_pairing':cal.frame_pairing,'width':cal.width,'height':cal.height,'points':uv[valid].tolist(),'boxes':boxes}
    @app.post('/api/v4/sessions/{sid}/image-detect')
    def image_detect(sid:str,payload:ImageRequest):
        store,s=session(sid)
        if s['revision']!=payload.revision:raise HTTPException(409,'Stale revision; reload before image detection')
        result={'revision':s['revision'],'point_fingerprint':fingerprint(store.points(sid)),'cameras':{},'errors':{}}
        for c in s['cameras']:
            path=camera(store,sid,c['index'])
            try:result['cameras'][str(c['index'])]={**image_detector.infer(path,payload.threshold),'image_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
            except (RuntimeError,ValueError,OSError) as error:result['errors'][str(c['index'])]=str(error)
        if store.load(sid)['revision']!=payload.revision:raise HTTPException(409,'Session changed while image inference ran; reload')
        return append_record(store.root,sid,'image-detections',result)
    @app.get('/api/v4/sessions/{sid}/image-detections')
    def get_detection(sid:str):
        store,s=session(sid);return read_latest(store.root,sid,'image-detections') or {'cameras':{},'errors':{}}
    @app.post('/api/v4/sessions/{sid}/evidence')
    def evidence(sid:str,payload:EvidenceRequest):
        store,s=session(sid);return evidence_data(store,s,payload.mapping,payload.topology)
    @app.post('/api/v4/sessions/{sid}/camera-candidate')
    def add_candidate(sid:str,payload:CandidateRequest):
        store,s=session(sid)
        if s['revision']!=payload.revision:raise HTTPException(409,'Stale revision')
        result=evidence_data(store,s,payload.mapping,payload.topology)
        item=next((r for r in result['candidates'].get(str(payload.camera_index),[]) if r['detection_id']==payload.detection_id),None)
        if not item or not item['proposal']:raise ValueError('No supported LiDAR candidate; review camera-only object manually')
        proposal=Cuboid(id=uuid4().hex,frame=(s.get('cvat') or {}).get('frame',0),**item['proposal'])
        current=[Cuboid(**b) for b in s['boxes']];merged=merge_proposals(current,[proposal],s['axis_convention'])
        # Merge helper returns review data; no automatic publication.
        return store.update(sid,payload.revision,merged[0] if isinstance(merged,tuple) else merged)
    @app.get('/api/v4/sessions/{sid}/measure')
    def measurement(sid:str,box_a:str,box_b:str|None=None):
        store,s=session(sid);lookup={b['id']:Cuboid(**b) for b in s['boxes']}
        if box_a not in lookup or box_b is not None and box_b not in lookup:raise HTTPException(404,'Measurement box not found')
        result=measure(lookup[box_a],lookup.get(box_b));meta=read_latest(store.root,sid,'metadata') or {}
        return {**result,'units':'m' if meta.get('units')=='metres' else 'sensor units','units_confirmed':meta.get('units')=='metres'}

# Apply session axis defaults to new proposals without changing merge's V3 contract.
_v3_merge_proposals=merge_proposals
def merge_proposals(existing,proposals,convention=None):
    if convention:
        for proposal in proposals:
            proposal.axis_order=list(convention['axis_order']);proposal.axis_signs=list(convention['axis_signs'])
    return _v3_merge_proposals(existing,proposals)
