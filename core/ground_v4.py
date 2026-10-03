"""Conservative local ground fit; raw input is never modified.
Mask: 0 unknown, 1 supported ground, 2 supported non-ground.
"""
from __future__ import annotations
import numpy as np
from .geometry import rotation_matrix

VERSION='local-ground-1'

def segment_ground(points, cell_size=2.0, tolerance=.08, max_slope=.35):
    xyz=np.asarray(points)[:,:3]
    if len(xyz)==0 or not np.isfinite(xyz).all(): raise ValueError('Ground input must be finite and nonempty')
    if not .5<=cell_size<=5 or not .02<=tolerance<=.2 or not 0<max_slope<=.6: raise ValueError('Invalid ground parameters')
    keys=np.floor(xyz[:,:2]/cell_size).astype(np.int64)
    unique,inverse=np.unique(keys,axis=0,return_inverse=True)
    order=np.argsort(inverse,kind='stable');cuts=np.searchsorted(inverse[order],np.arange(len(unique)+1))
    groups={tuple(key):order[cuts[i]:cuts[i+1]] for i,key in enumerate(unique)}
    mask=np.zeros(len(xyz),dtype=np.uint8);cells={}
    for key,indices in groups.items():
        if len(indices)<8: continue
        local=xyz[indices];q=np.quantile(local[:,2],.2)
        seeds=local[local[:,2]<=q+tolerance]
        if len(seeds)<6:continue
        centered=seeds[:,:2]-seeds[:,:2].mean(axis=0)
        if np.linalg.matrix_rank(centered)<2 or np.linalg.eigvalsh(centered.T@centered/len(seeds))[0]<.015:continue
        design=np.column_stack((seeds[:,:2],np.ones(len(seeds))))
        coef=np.linalg.lstsq(design,seeds[:,2],rcond=None)[0]
        if np.linalg.norm(coef[:2])>max_slope:continue
        nearby=[]
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                ids=groups.get((key[0]+dx,key[1]+dy))
                if ids is not None and len(ids)>=8:
                    neighbor=xyz[ids];height=np.quantile(neighbor[:,2],.2)
                    near=neighbor[neighbor[:,2]<=height+tolerance]
                    nearby.extend((near[:,2]-near[:,:2]@coef[:2]).tolist())
        if nearby and coef[2]>np.quantile(nearby,.2)+.25:continue
        # Refine using all near-plane returns to avoid a low-quantile bias.
        residual=local[:,2]-np.column_stack((local[:,:2],np.ones(len(local))))@coef
        support=np.abs(residual)<=tolerance
        if support.sum()<8:continue
        fitted=local[support];coef=np.linalg.lstsq(np.column_stack((fitted[:,:2],np.ones(len(fitted)))),fitted[:,2],rcond=None)[0]
        residual=local[:,2]-np.column_stack((local[:,:2],np.ones(len(local))))@coef
        if np.quantile(np.abs(residual[support]),.9)>tolerance:continue
        # Below-plane returns remain unknown rather than being erased.
        mask[indices[np.abs(residual)<=tolerance]]=1
        mask[indices[residual>tolerance]]=2
        cells[key]=[float(x) for x in coef]+[int(np.sum(mask[indices]==1))]
    return {'mask':mask,'cells':cells,'cell_size':float(cell_size),'version':VERSION}

def ground_surface(result, limit=6000):
    size=result['cell_size'];cells=result['cells'];triangles=[]
    for (x,y),coef in cells.items():
        if len(triangles)>=limit:break
        # Average supported neighboring fits at shared vertices, but reject steps.
        vertices=[]
        for dx,dy in ((0,0),(1,0),(1,1),(0,1)):
            px,py=(x+dx)*size,(y+dy)*size
            heights=[c[0]*px+c[1]*py+c[2] for (kx,ky),c in cells.items() if kx in (x+dx-1,x+dx) and ky in (y+dy-1,y+dy)]
            own=coef[0]*px+coef[1]*py+coef[2]
            valid=[h for h in heights if abs(h-own)<=.15]
            vertices.append([px,py,float(np.mean(valid)) if valid else own])
        triangles.extend([[vertices[0],vertices[1],vertices[2]],[vertices[0],vertices[2],vertices[3]]])
    return triangles

def ground_contact(box, result):
    bottom=np.array([[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1]])*np.array(box.size)/2
    corners=bottom@rotation_matrix(box.roll,box.pitch,box.yaw).T+box.center
    differences=[]
    for x,y,z in corners:
        key=tuple(np.floor(np.array([x,y])/result['cell_size']).astype(int))
        coef=result['cells'].get(key)
        if coef is None:return {'available':False,'reason':'Ground thiếu support quanh đáy box'}
        differences.append(float(z-(coef[0]*x+coef[1]*y+coef[2])))
    return {'available':True,'clearance_m':float(np.median(differences)),'minimum_clearance_m':min(differences),'source':VERSION}

# Use bounded neighbor lookup for large scans; preserve prior source for review.
from .surface_v4 import ground_surface
