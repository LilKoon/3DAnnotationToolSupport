"""Distances in raw sensor units; all roll/pitch/yaw corners are respected."""
import numpy as np
from .camera_v4 import box_corners

def footprint_xy(box):
    points=sorted(set(map(tuple,box_corners(box)[:,:2])))
    def cross(o,a,b):return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    lower=[];upper=[]
    for p in points:
        while len(lower)>=2 and cross(lower[-2],lower[-1],p)<=0:lower.pop()
        lower.append(p)
    for p in reversed(points):
        while len(upper)>=2 and cross(upper[-2],upper[-1],p)<=0:upper.pop()
        upper.append(p)
    return np.array(lower[:-1]+upper[:-1])

def polygon_gap(a,b):
    separated=False
    for poly in (a,b):
        for i,p in enumerate(poly):
            edge=poly[(i+1)%len(poly)]-p;axis=np.array([-edge[1],edge[0]])
            if max(a@axis)<min(b@axis)-1e-10 or max(b@axis)<min(a@axis)-1e-10:separated=True
    if not separated:return 0.
    distance=float('inf')
    for points,poly in ((a,b),(b,a)):
        for point in points:
            for i,p in enumerate(poly):
                edge=poly[(i+1)%len(poly)]-p;length=float(edge@edge)
                t=float(np.clip((point-p)@edge/length,0,1)) if length else 0.
                distance=min(distance,float(np.linalg.norm(point-(p+t*edge))))
    return distance

def measure(a,b=None):
    result={'sensor_center_3d':float(np.linalg.norm(a.center)),'source':'LiDAR cuboid geometry','units':'sensor units'}
    if b is not None:
        delta=np.array(a.center)-b.center
        result.update(center_3d=float(np.linalg.norm(delta)),center_xy=float(np.linalg.norm(delta[:2])),gap_xy=polygon_gap(footprint_xy(a),footprint_xy(b)))
    return result
