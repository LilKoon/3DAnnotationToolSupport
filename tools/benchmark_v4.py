"""Read-only V3 fixtures; immutable performance report in V4."""
import json,time,hashlib,platform,resource,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.ground_v4 import segment_ground,ground_surface
from core.image_detector_v4 import image_detector
root=Path(__file__).resolve().parents[1];source=root.parent/'v3/data/sessions'
clouds=[p for p in source.glob('*.npy') if not p.name.endswith('.colors.npy') and p.stat().st_size>1000000]
clouds=sorted(clouds,key=lambda p:p.name)[:3];results=[]
for path in clouds:
    pts=np.load(path,allow_pickle=False);before=hashlib.sha256(path.read_bytes()).hexdigest();start=time.perf_counter();ground=segment_ground(pts);seg=time.perf_counter()-start;start=time.perf_counter();tiles=ground_surface(ground);surface=time.perf_counter()-start
    assert before==hashlib.sha256(path.read_bytes()).hexdigest()
    results.append({'source':path.name,'points':len(pts),'ground_ms':round(seg*1000,2),'surface_ms':round(surface*1000,2),'ground_points':int(np.sum(ground['mask']==1)),'unknown_points':int(np.sum(ground['mask']==0)),'triangles':len(tiles),'surface_truncated':len(ground['cells'])>3000})
image=root.parent/'venv/lib/python3.13/site-packages/ultralytics/assets/bus.jpg';start=time.perf_counter();det=image_detector.infer(image);elapsed=time.perf_counter()-start
report={'machine':platform.platform(),'python':sys.version.split()[0],'pointclouds':results,'image_smoke':{'fixture':'local Ultralytics bus.jpg','model':det['model'],'detections':len(det['detections']),'classes':sorted(set(d['label'] for d in det['detections'])),'elapsed_ms':round(elapsed*1000,2),'checkpoint_sha256':det['checkpoint_sha256']},'peak_process_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'accuracy_claim':'No ground-truth calibration or held-out annotation supplied; counts are not accuracy metrics.'}
out=root/'data/verification'/str(time.time_ns());out.mkdir(parents=True,exist_ok=False)
with (out/'benchmark.json').open('x') as stream:json.dump(report,stream,indent=2)
print(json.dumps(report,indent=2));print('Report:',out/'benchmark.json')
