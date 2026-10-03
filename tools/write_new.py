"""Create or append V4 files; never overwrite or delete. Paths confined to V4."""
import json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
payload=json.loads(sys.argv[1])
for item in payload:
    relative=Path(item["path"])
    if relative.is_absolute() or ".." in relative.parts: raise SystemExit("Invalid path")
    target=root/relative
    if not target.resolve().is_relative_to(root): raise SystemExit("Path outside V4")
    if item.get("mode","create") not in ("create","append"): raise SystemExit("Invalid mode")
    if item.get("mode","create")=="create" and target.exists(): raise SystemExit("Already exists: "+str(target))
for item in payload:
    target=root/item["path"]
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open("a" if item.get("mode")=="append" else "x",encoding="utf-8") as output:
        output.write(item["content"])
    print(item.get("mode","create")+": "+str(target.relative_to(root)))
