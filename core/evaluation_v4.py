"""Annotation assistance diagnostics; explicitly not benchmark mAP."""
import math
import numpy as np
from scipy.optimize import linear_sum_assignment
from .geometry import rotation_matrix
from .detector_evaluation import score_predictions
from .proposal_review import cuboid_iou

def upright(box):return abs(box.pitch)<1e-8 and abs(box.roll)<1e-8

def compare_annotations(predictions,truth,distance_limit=2.):
    report=score_predictions(predictions,truth,distance_limit);angles=[];ious=[]
    for label in {b.label for b in predictions+truth}:
        p=[b for b in predictions if b.label==label];g=[b for b in truth if b.label==label]
        if not p or not g:continue
        distances=np.linalg.norm(np.array([b.center for b in p])[:,None,:]-np.array([b.center for b in g])[None,:,:],axis=2)
        a,b=linear_sum_assignment(np.where(distances<=distance_limit,distances,1e6))
        for i,j in zip(a,b):
            if distances[i,j]>distance_limit:continue
            rp=rotation_matrix(p[i].roll,p[i].pitch,p[i].yaw);rg=rotation_matrix(g[j].roll,g[j].pitch,g[j].yaw)
            angles.append(math.degrees(math.acos(float(np.clip((np.trace(rp.T@rg)-1)/2,-1,1)))))
            if upright(p[i]) and upright(g[j]):ious.append(cuboid_iou(p[i],g[j]))
    return {**report,'protocol':f'one-to-one same-label center matching <= {distance_limit} sensor units; not mAP','rotation_error_deg':float(np.mean(angles)) if angles else None,'mean_iou3d':float(np.mean(ious)) if ious else None,'iou_supported_pairs':len(ious),'matched_pairs':len(angles),'iou_limit':'upright yaw boxes only; pitch/roll pairs excluded'}

def quality_report(boxes):
    if len(boxes)>2000:raise ValueError('Quality report limited to 2000 boxes')
    overlapping=[];unsupported=[]
    for i,a in enumerate(boxes):
        if not upright(a):unsupported.append(a.id)
        for b in boxes[i+1:]:
            if upright(a) and upright(b) and np.linalg.norm(np.array(a.center)-b.center)<=sum(a.size)+sum(b.size) and cuboid_iou(a,b)>=.5:overlapping.append([a.id,b.id])
    return {'box_count':len(boxes),'pending':sum(b.status=='pending' for b in boxes),'accepted':sum(b.status=='accepted' for b in boxes),'overlapping_pairs':overlapping,'tilted_iou_unsupported':unsupported,'note':'Overlapping boxes are review hints, not automatically deleted.'}
