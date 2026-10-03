"""Review backups fork into new sessions; current data is never replaced."""
from typing import Literal
import hashlib
from fastapi import HTTPException
from pydantic import BaseModel,Field,ConfigDict
from core.geometry import Cuboid
from core.camera_v4 import Calibration
from core.derived_v4 import fingerprint,read_latest,append_record
from api.ground_routes_v4 import MetadataRequest

class RestoreRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    format:Literal['v4-review']
    point_fingerprint:str
    session:dict
    metadata:MetadataRequest|None=None
    calibration:dict[str,Calibration]=Field(default_factory=dict)
    image_detections:dict|None=None
    camera_sha256:dict[str,str]=Field(default_factory=dict)

def install(app,get_store):
    def session(sid):
        store=get_store()
        try:return store,store.load(sid)
        except FileNotFoundError:raise HTTPException(404,'Session not found')
    @app.get('/api/v4/sessions/{sid}/review-backup')
    def backup(sid:str):
        store,s=session(sid)
        return {'format':'v4-review','point_fingerprint':fingerprint(store.points(sid)),'session':s,'metadata':read_latest(store.root,sid,'metadata'),'calibration':read_latest(store.root,sid,'calibration') or {},'image_detections':read_latest(store.root,sid,'image-detections'),'camera_sha256':{str(c['index']):hashlib.sha256(store.camera_path(sid,c['index']).read_bytes()).hexdigest() for c in s['cameras']}}
    @app.post('/api/v4/sessions/{sid}/restore-review')
    def restore(sid:str,payload:RestoreRequest):
        store,current=session(sid);points=store.points(sid)
        if payload.point_fingerprint!=fingerprint(points):raise ValueError('Backup belongs to a different point cloud; open the original frame first')
        if payload.session.get('cvat')!=current.get('cvat'):raise ValueError('Backup CVAT binding differs from current job/frame')
        raw_boxes=payload.session.get('boxes',[])
        if not isinstance(raw_boxes,list) or len(raw_boxes)>2000:raise ValueError('Backup limited to 2000 boxes')
        boxes=[Cuboid(**b) for b in raw_boxes]
        if len({b.id for b in boxes})!=len(boxes) or any(b.label not in current['labels'] for b in boxes):raise ValueError('Backup contains duplicate IDs or labels outside the current job')
        images={str(c['index']):(c,store.camera_path(sid,c['index']).read_bytes()) for c in current['cameras']}
        for index,digest in payload.camera_sha256.items():
            if index not in images or hashlib.sha256(images[index][1]).hexdigest()!=digest:raise ValueError('Backup camera images differ; attach matching images before restoring')
        if any(index not in payload.camera_sha256 for index in payload.calibration):raise ValueError('Calibration restore requires matching image fingerprints')
        created=store.create(points,current['title']+' · restored',current['labels'],current.get('cvat'),colors=store.colors(sid))
        for index,(cam,data) in sorted(images.items(),key=lambda pair:int(pair[0])):created=store.add_camera(created['id'],cam['name'],data)
        created=store.update(created['id'],created['revision'],boxes)
        for field in ('label_specs','axis_convention','published_ids'):
            if field in current:created[field]=current[field]
        created['restored_from']=sid;created['revision']+=1;store.save(created)
        if payload.metadata:append_record(store.root,created['id'],'metadata',payload.metadata.model_dump())
        if payload.calibration:append_record(store.root,created['id'],'calibration',{k:v.model_dump() for k,v in payload.calibration.items()})
        if payload.image_detections:append_record(store.root,created['id'],'image-detections',payload.image_detections)
        return created
