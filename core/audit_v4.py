"""Report observed data separately from confirmed sensor metadata."""
import numpy as np

def audit_input(points, session, metadata=None, calibration=None):
    xyz=np.asarray(points)[:,:3];metadata=metadata or {};calibration=calibration or {}
    cameras=session.get('cameras',[])
    ready=bool(cameras) and all(str(c['index']) in calibration and calibration[str(c['index'])].get('reviewed') and calibration[str(c['index'])].get('frame_pairing')=='confirmed' for c in cameras)
    units=metadata.get('units')=='metres' and metadata.get('axes')=='x-forward-y-left-z-up'
    return {'point_count':len(xyz),'display_limit':100000,'xyz_min':xyz.min(axis=0).tolist(),'xyz_max':xyz.max(axis=0).tolist(),'camera_count':len(cameras),'units_confirmed':units,'fusion_ready':bool(ready and units),'units':metadata.get('units','unknown'),'axes':metadata.get('axes','unknown'),'warnings':([] if units else ['Chưa xác nhận đơn vị mét và hệ trục LiDAR; kiểm tra nguồn dataset'])+([] if ready else ['Camera chỉ tham khảo cho đến khi calibration và đồng bộ được kiểm chứng'])}
