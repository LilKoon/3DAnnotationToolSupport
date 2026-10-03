"""Immutable record journal; invalid or interrupted records never hide valid history."""
import json
from time import time_ns
from uuid import uuid4
from pathlib import Path

def read_latest(root,session_id,kind):
    for path in sorted((Path(root)/session_id/'v4'/kind).glob('*.json'),reverse=True):
        try:return json.loads(path.read_text())
        except (ValueError,OSError):continue
    return None

def append_record(root,session_id,kind,data):
    payload=json.dumps(data,ensure_ascii=False,allow_nan=False)
    path=Path(root)/session_id/'v4'/kind;path.mkdir(parents=True,exist_ok=True)
    with (path/f'{time_ns():020d}-{uuid4().hex}.json').open('x') as output:output.write(payload)
    return data
