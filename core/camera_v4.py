"""Pinhole calibration, projection and conservative image evidence."""
from __future__ import annotations
from typing import Literal
from itertools import product
import numpy as np
from pydantic import BaseModel,Field,model_validator,ConfigDict
from .geometry import rotation_matrix

class Calibration(BaseModel):
    model_config=ConfigDict(extra='forbid')
    K:list[list[float]]
    T_camera_from_lidar:list[list[float]]
    width:int=Field(gt=0,le=20000)
    height:int=Field(gt=0,le=20000)
    camera_id:str=Field(default='camera',max_length=100)
    model:Literal['pinhole']='pinhole'
    distortion:list[float]=Field(default_factory=lambda:[0.,0.,0.,0.,0.],min_length=5,max_length=5)
    units:Literal['metres']='metres'
    reviewed:bool=False
    frame_pairing:Literal['confirmed','unknown']='unknown'
    @model_validator(mode='after')
    def matrices(self):
        k=np.array(self.K);t=np.array(self.T_camera_from_lidar)
        if k.shape!=(3,3) or t.shape!=(4,4) or not np.isfinite(k).all() or not np.isfinite(t).all():raise ValueError('Invalid matrix shapes/values')
        if k[0,0]<=0 or k[1,1]<=0 or not np.allclose(k[2],[0,0,1]) or abs(k[1,0])>1e-8:raise ValueError('Invalid pinhole intrinsics')
        if not np.allclose(t[3],[0,0,0,1]) or not np.allclose(t[:3,:3].T@t[:3,:3],np.eye(3),atol=1e-5) or not np.isclose(np.linalg.det(t[:3,:3]),1,atol=1e-5):raise ValueError('Extrinsics must be proper rigid transform')
        if not np.isfinite(self.distortion).all() or max(abs(x) for x in self.distortion)>10:raise ValueError('Invalid distortion')
        return self

def camera_coordinates(points,cal):
    xyz=np.asarray(points)[:,:3];t=np.asarray(cal.T_camera_from_lidar)
    return xyz@t[:3,:3].T+t[:3,3]

def camera_pixels(camera,cal):
    depth=camera[:,2];z=np.where(depth>.001,depth,.001)
    x,y=camera[:,0]/z,camera[:,1]/z;k1,k2,p1,p2,k3=cal.distortion
    r2=np.clip(x*x+y*y,0,1e6);radial=1+k1*r2+k2*r2*r2+k3*r2*r2*r2
    xd=x*radial+2*p1*x*y+p2*(r2+2*x*x);yd=y*radial+p1*(r2+2*y*y)+2*p2*x*y
    k=np.asarray(cal.K);return np.column_stack((k[0,0]*xd+k[0,1]*yd+k[0,2],k[1,1]*yd+k[1,2]))

def project_points(points,cal):
    cam=camera_coordinates(points,cal);uv=camera_pixels(cam,cal);depth=cam[:,2]
    valid=(depth>=.1)&np.isfinite(uv).all(axis=1)&(uv[:,0]>=0)&(uv[:,0]<cal.width)&(uv[:,1]>=0)&(uv[:,1]<cal.height)
    return uv,depth,valid

def box_corners(box):
    local=np.array(list(product((-1,1),repeat=3)))*np.asarray(box.size)/2
    return local@rotation_matrix(box.roll,box.pitch,box.yaw).T+box.center

def project_box(box,cal):
    cam=camera_coordinates(box_corners(box),cal);edges=[];vertices=[]
    for i in range(8):
        for bit in (1,2,4):
            j=i^bit
            if j<i:continue
            a,b=cam[i].copy(),cam[j].copy()
            if a[2]<.1 and b[2]<.1:continue
            if a[2]<.1:a=a+(.1-a[2])/(b[2]-a[2])*(b-a)
            if b[2]<.1:b=b+(.1-b[2])/(a[2]-b[2])*(a-b)
            pixel=camera_pixels(np.array([a,b]),cal)
            if not np.isfinite(pixel).all():continue
            vertices.extend(pixel.tolist());edges.append(pixel.tolist())
    if not vertices:return None
    v=np.asarray(vertices);low=np.maximum(v.min(axis=0),[0,0]);high=np.minimum(v.max(axis=0),[cal.width,cal.height])
    if np.any(high<=low):return None
    return {'box_id':box.id,'label':box.label,'bbox':[*low.tolist(),*high.tolist()],'edges':edges,'depth':float(np.mean(cam[:,2]))}

def bbox_iou(a,b):
    a=np.asarray(a);b=np.asarray(b);wh=np.maximum(0,np.minimum(a[2:],b[2:])-np.maximum(a[:2],b[:2]));inter=float(np.prod(wh))
    union=float(np.prod(np.maximum(a[2:]-a[:2],0))+np.prod(np.maximum(b[2:]-b[:2],0))-inter)
    return inter/union if union>0 else 0.

def associate(boxes,detections,cal,mapping,points=None):
    projections=[(b,project_box(b,cal)) for b in boxes if b.status!='rejected'];rows=[];used=set()
    ready=cal.reviewed and cal.frame_pairing=='confirmed'
    for d in sorted(detections,key=lambda item:-item.get('confidence',0)):
        row={'detection_id':d['id'],'label':d['label'],'bbox':d['bbox'],'confidence':d.get('confidence'),'box_id':None,'status':'reference_only','evidence':'image_geometry'}
        if ready:
            target=mapping.get(d['label']);scores=[]
            for box,proj in projections:
                if proj is None or box.id in used or target!=box.label:continue
                score=bbox_iou(d['bbox'],proj['bbox'])
                if score>=.2:
                    if points is not None:
                        local=(np.asarray(points)[:,:3]-box.center)@rotation_matrix(box.roll,box.pitch,box.yaw)
                        count=int(np.sum(np.all(np.abs(local)<=np.array(box.size)/2+.1,axis=1)))
                        if count<3:continue
                    scores.append((score,box.id))
            scores.sort(reverse=True);row['status']='unmatched' if target else 'unsupported_label'
            if scores:
                if len(scores)>1 and scores[0][0]-scores[1][0]<.05:row['status']='ambiguous'
                else:row.update(box_id=scores[0][1],status='matched',overlap=scores[0][0]);used.add(scores[0][1])
        rows.append(row)
    return rows
