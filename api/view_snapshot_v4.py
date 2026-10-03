"""Exclusive local view images; annotation and source clouds are unchanged."""
import base64,binascii,io,re
from uuid import uuid4
from PIL import Image,UnidentifiedImageError
from fastapi import HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel,Field,ConfigDict
class SnapshotRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    png:str=Field(min_length=1,max_length=6000000)
def install(app,get_store):
    def directory(sid):
        store=get_store()
        try:store.load(sid)
        except (FileNotFoundError,ValueError):raise HTTPException(404,'Session not found')
        return store.root/sid/'v4'/'view_snapshots'
    @app.post('/api/v4/sessions/{sid}/view-snapshot')
    def save(sid:str,payload:SnapshotRequest):
        folder=directory(sid)
        try:
            data=base64.b64decode(payload.png,validate=True)
            with Image.open(io.BytesIO(data)) as image:
                if image.format!='PNG' or image.width>8000 or image.height>8000 or image.width*image.height>16000000:raise ValueError('Invalid image size or format')
                image.verify()
        except (binascii.Error,ValueError,UnidentifiedImageError,OSError):raise HTTPException(400,'Invalid PNG image')
        folder.mkdir(parents=True,exist_ok=True);key=uuid4().hex
        with (folder/(key+'.png')).open('xb') as output:output.write(data)
        return {'url':f'/api/v4/sessions/{sid}/view-snapshots/{key}'}
    @app.get('/api/v4/sessions/{sid}/view-snapshots/{key}')
    def read(sid:str,key:str):
        folder=directory(sid)
        if not re.fullmatch(r'[0-9a-f]{32}',key):raise HTTPException(404,'Image not found')
        file=folder/(key+'.png')
        if not file.is_file():raise HTTPException(404,'Image not found')
        return FileResponse(file,media_type='image/png',filename='v4-ground-view-'+key+'.png')
