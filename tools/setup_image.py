"""Download official YOLO11n once; never replace existing weights."""
from pathlib import Path
from urllib.request import urlopen
import hashlib
root=Path(__file__).resolve().parents[1];target=root/'models/yolo11n.pt'
if target.exists():
    print('Checkpoint already exists; preserved:',target)
else:
    url='https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt'
    with urlopen(url,timeout=60) as response:data=response.read(40*1024*1024)
    if len(data)<1000000:raise SystemExit('Invalid checkpoint response')
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as output:output.write(data)
    print('Downloaded official YOLO11n:',len(data),'bytes; sha256',hashlib.sha256(data).hexdigest())
