"""Bounded neighbor lookup for local ground tiles."""
import numpy as np

def ground_surface(result,limit=6000):
    size=result['cell_size'];cells=result['cells'];triangles=[]
    for (x,y),coef in cells.items():
        if len(triangles)>=limit:break
        vertices=[]
        for dx,dy in ((0,0),(1,0),(1,1),(0,1)):
            px,py=(x+dx)*size,(y+dy)*size;own=coef[0]*px+coef[1]*py+coef[2]
            heights=[]
            for kx in (x+dx-1,x+dx):
                for ky in (y+dy-1,y+dy):
                    c=cells.get((kx,ky))
                    if c is not None:
                        h=c[0]*px+c[1]*py+c[2]
                        if abs(h-own)<=.15:heights.append(h)
            vertices.append([px,py,float(np.mean(heights)) if heights else own])
        triangles.extend([[vertices[0],vertices[1],vertices[2]],[vertices[0],vertices[2],vertices[3]]])
    return triangles
