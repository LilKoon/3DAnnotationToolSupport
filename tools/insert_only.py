"""Insert text only; preserve all existing bytes, with no deletion/truncation."""
import json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
item=json.loads(sys.argv[1]);target=root/item['path']
if not target.resolve().is_relative_to(root):raise SystemExit('Outside V4')
old=target.read_bytes();marker=item['before'].encode();addition=item['content'].encode()
if old.count(marker)!=1:raise SystemExit('Marker must be unique')
index=old.index(marker);new=old[:index]+addition+old[index:]
with target.open('r+b') as output:output.write(new)
print('Inserted without removing existing bytes:',item['path'])
