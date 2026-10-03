"""Content-addressed append-only derived artifacts; no cleanup or overwrites."""
import hashlib,json,threading
from pathlib import Path
import numpy as np
from .ground_v4 import segment_ground,ground_surface,VERSION

_lock=threading.RLock()

def fingerprint(points):
    a=np.ascontiguousarray(points)
    return hashlib.sha256(str(a.shape).encode()+str(a.dtype).encode()+a.tobytes()).hexdigest()

def read_latest(root,session_id,kind):
    paths=sorted((Path(root)/session_id/'v4'/kind).glob('*.json'))
    return json.loads(paths[-1].read_text()) if paths else None

def append_record(root,session_id,kind,data):
    from time import time_ns
    from uuid import uuid4
    path=Path(root)/session_id/'v4'/kind
    path.mkdir(parents=True,exist_ok=True)
    target=path/f'{time_ns():020d}-{uuid4().hex}.json'
    with target.open('x') as output:json.dump(data,output,ensure_ascii=False,allow_nan=False)
    return data

def ground_record(root,session_id,points,cell_size=2.,tolerance=.08):
    key=hashlib.sha256(f'{fingerprint(points)}:{VERSION}:{cell_size}:{tolerance}'.encode()).hexdigest()
    path=Path(root)/session_id/'v4'/'ground'/f'{key}.json'
    with _lock:
        if path.exists():return json.loads(path.read_text())
        result=segment_ground(points,cell_size,tolerance)
        stride=max(1,int(np.ceil(len(points)/100000)))
        record={'fingerprint':fingerprint(points),'cache_key':key,'version':VERSION,'cell_size':cell_size,'tolerance':tolerance,'display_mask':result['mask'][::stride].tolist(),'display_indices':list(range(0,len(points),stride)),'counts':{'unknown':int(np.sum(result['mask']==0)),'ground':int(np.sum(result['mask']==1)),'non_ground':int(np.sum(result['mask']==2))},'cells':[[*key,*value] for key,value in result['cells'].items()],'surface':ground_surface(result)}
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('x') as output:json.dump(record,output,allow_nan=False)
        return record

def restore_ground(record):
    return {'cells':{tuple(row[:2]):row[2:] for row in record['cells']},'cell_size':record['cell_size'],'version':record['version']}

# V2 cache serializer prepares valid JSON before creating an immutable artifact.
from .ground_cache_v4 import ground_record

from .artifacts_v4 import read_latest,append_record
