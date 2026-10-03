"""Camera-guided 3D candidates require supported non-ground LiDAR clusters."""
import numpy as np
from scipy.spatial import cKDTree
from .camera_v4 import project_points
from .ground_v4 import segment_ground

def candidates(points,rows,cal,min_points=12):
    xyz=np.asarray(points)[:,:3];uv,depth,valid=project_points(xyz,cal);mask=segment_ground(points)['mask'];results=[]
    for row in rows:
        if row['status']!='unmatched':continue
        x1,y1,x2,y2=row['bbox'];inside=valid&(uv[:,0]>=x1)&(uv[:,0]<=x2)&(uv[:,1]>=y1)&(uv[:,1]<=y2)&(mask==2)
        ids=np.flatnonzero(inside)
        result={'detection_id':row['detection_id'],'label':row.get('target_label',row['label']),'status':'insufficient_lidar','proposal':None,'point_count':int(len(ids))}
        if len(ids)>=min_points:
            # Bound clustering; contiguous sensor depth alone does not join distant objects.
            ids=ids[::max(1,int(np.ceil(len(ids)/8000)))];cloud=xyz[ids];tree=cKDTree(cloud);seen=set();clusters=[]
            for seed in range(len(cloud)):
                if seed in seen:continue
                pending=[seed];seen.add(seed);cluster=[]
                while pending:
                    i=pending.pop();cluster.append(i)
                    for j in tree.query_ball_point(cloud[i],.6):
                        if j not in seen:seen.add(j);pending.append(j)
                if len(cluster)>=min_points:clusters.append(cluster)
            if len(clusters)>1:result['status']='ambiguous_lidar'
            elif len(clusters)==1:
                cluster=cloud[clusters[0]];low=cluster.min(axis=0);high=cluster.max(axis=0);size=high-low
                if np.all(size>=[.15,.15,.3]) and np.all(size<=[15,8,6]):
                    result.update(status='supported_candidate',proposal={'label':result['label'],'center':((high+low)/2).tolist(),'size':size.tolist(),'yaw':0.,'source':'camera-guided-lidar-cluster','status':'pending'},point_count=len(cluster))
                else:result['status']='ambiguous_geometry'
        results.append(result)
    return results
