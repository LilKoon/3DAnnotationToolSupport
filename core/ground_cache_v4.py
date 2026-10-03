"""Serialize a complete payload before opening a new cache file."""
import hashlib,json,threading
from uuid import uuid4
from pathlib import Path
import numpy as np
from .ground_v4 import segment_ground,ground_surface,VERSION
from .derived_v4 import fingerprint
_lock=threading.RLock()

def ground_record(root,session_id,points,cell_size=2.,tolerance=.08):
    source=fingerprint(points);key=hashlib.sha256(f'{source}:{VERSION}:cache2:{cell_size}:{tolerance}'.encode()).hexdigest()
    directory=Path(root)/session_id/'v4'/'ground'
    with _lock:
        for path in directory.glob(key+'-*.json'):
            try:return json.loads(path.read_text())
            except (ValueError,OSError):continue
        result=segment_ground(points,cell_size,tolerance);stride=max(1,int(np.ceil(len(points)/100000)))
        record={'fingerprint':source,'cache_key':key,'version':VERSION,'cell_size':cell_size,'tolerance':tolerance,'display_mask':result['mask'][::stride].tolist(),'display_indices':list(range(0,len(points),stride)),'counts':{'unknown':int(np.sum(result['mask']==0)),'ground':int(np.sum(result['mask']==1)),'non_ground':int(np.sum(result['mask']==2))},'cells':[[int(k[0]),int(k[1]),*v] for k,v in result['cells'].items()],'surface':ground_surface(result)}
        content=json.dumps(record,allow_nan=False);directory.mkdir(parents=True,exist_ok=True)
        with (directory/f'{key}-{uuid4().hex}.json').open('x') as output:output.write(content)
        return record
