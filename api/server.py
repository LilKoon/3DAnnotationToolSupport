from __future__ import annotations

from pathlib import Path
from typing import Literal
import hashlib
import json
from uuid import uuid4
from urllib.parse import urlparse
from io import BytesIO
from zipfile import ZipFile
import numpy as np

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from cvat_sdk.api_client.exceptions import ApiException

from core.geometry import Cuboid, cvat_points, AxisConvention, axis_attributes, cvat_oriented_box
from core.models import configured_models, detect
from core.pointcloud import MAX_BYTES, display_points, parse_pointcloud
from core.store import SessionStore
from core.detector_service import detector_service
from core.lidar_presets import GUIDELINE_LABELS, PRESETS, validate_label_map
from core.proposal_review import merge_proposals
from core.label_mapping import default_mapping, filter_proposals
from core.detector_evaluation import PROFILES, score_predictions, aggregate_scores

ROOT = Path(__file__).resolve().parents[1]
store = SessionStore(ROOT / "data" / "sessions")
app = FastAPI(title="CVAT 3D Annotation V4")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

import os
# Default hash for "lilkoon"
ACCESS_KEY_HASH = os.environ.get("V4_ACCESS_KEY_HASH", "1685a500b7fd5b9f181fc463488a47642fe0b0fc34299bcf9a196393b165e608")

@app.middleware("http")
async def verify_access_key(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        # Allow preflight requests
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # Check header or query param
        auth_header = request.headers.get("Authorization")
        key = None
        if auth_header and auth_header.startswith("Bearer "):
            key = auth_header.split(" ")[1]
        if not key:
            key = request.query_params.get("access_key")
            
        if not key or hashlib.sha256(key.encode()).hexdigest() != ACCESS_KEY_HASH:
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing Access Key"})
            
    return await call_next(request)


class Credentials(BaseModel):
    url: str
    username: str
    password: str
    job_id: int = Field(gt=0)
    verify_ssl: bool = True

    def connect(self):
        parsed = urlparse(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("CVAT URL must be http or https")
        from cvat_sdk import Config
        from cvat_sdk.core.client import Client
        client = Client(self.url.rstrip("/"), config=Config(verify_ssl=self.verify_ssl))
        client.login((self.username, self.password))
        return client, client.jobs.retrieve(self.job_id)


class JobFrame(Credentials):
    frame: int


class SaveRequest(BaseModel):
    revision: int = Field(ge=0)
    boxes: list[Cuboid]


class DetectRequest(BaseModel):
    revision: int = Field(ge=0)
    model_id: str
    threshold: float = Field(default=0.3, ge=0, le=1)
    label_map: dict[str, str] = Field(default_factory=dict)
    class_thresholds: dict[str, float] = Field(default_factory=dict)
    profile: Literal['precise','balanced','recall','custom'] = 'custom'
    mode: Literal['append', 'replace'] = 'append'


class DetectorSettingsRequest(BaseModel):
    mode: str = "remote"
    url: str = ""
    api_token: str | None = None
    intensity_scale: float = Field(default=1.0, gt=0, le=1000)


class GuidelineRequest(BaseModel):
    revision: int = Field(ge=0)


class BoxArchiveRequest(BaseModel):
    revision: int = Field(ge=0)
    restore: bool = False


class AxisConventionRequest(BaseModel):
    revision: int = Field(ge=0)
    convention: AxisConvention
    apply_existing: bool = False


class PublishRequest(Credentials):
    confirm: bool = False
    mode: Literal['append', 'replace'] = 'append'
    revision: int | None = None
    replacement_token: str | None = None


def annotation_token(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def cvat_replacement_data(value):
    """CVAT PUT creates new annotation IDs, including nested element IDs."""
    if isinstance(value, dict):
        return {key: cvat_replacement_data(item) for key, item in value.items() if key != 'id'}
    if isinstance(value, list):
        return [cvat_replacement_data(item) for item in value]
    return value


@app.exception_handler(ApiException)
async def cvat_api_error(_, error: ApiException):
    status = error.status if error.status and 400 <= error.status < 500 else 502
    detail = str(error.body or error.reason or 'Không nhận được phản hồi hợp lệ')[:3000]
    return JSONResponse(status_code=status, content={'detail': f'CVAT HTTP {error.status}: {detail}'})


@app.post('/api/sessions/{session_id}/publish-preview')
def publish_preview(session_id: str, payload: Credentials):
    try:
        session = store.load(session_id)
        binding = session.get('cvat')
        if not binding or binding['url'] != payload.url.rstrip('/') or binding['job_id'] != payload.job_id:
            raise ValueError('CVAT connection does not match this session')
        for item in session['boxes']:
            if item['status'] == 'accepted':
                cvat_oriented_box(Cuboid(**item))
        _, job = payload.connect()
        data = job.get_annotations().to_dict()
        targets = [{'id': shape['id'], 'label_id': shape['label_id'], 'type': shape['type']} for shape in data.get('shapes', []) if shape['frame'] == binding['frame']]
        for track in data.get('tracks', []):
            for shape in track['shapes']:
                if shape['frame'] == binding['frame']:
                    targets.append({'id': track['id'], 'label_id': track['label_id'], 'type': 'track_cuboid'})
        return {'frame': binding['frame'], 'job_id': binding['job_id'], 'targets': targets, 'replacement_token': annotation_token(data), 'revision': session['revision']}
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(400, str(error))


@app.exception_handler(ValueError)
async def invalid_input(_, error: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(error)})


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/models")
def models():
    return configured_models()


@app.get("/api/detector/settings")
def detector_settings():
    return detector_service.public_settings()


@app.post("/api/detector/settings")
def configure_detector(payload: DetectorSettingsRequest):
    return detector_service.configure(payload.mode, payload.url, payload.api_token, payload.intensity_scale)


@app.post("/api/detector/check")
def check_detector():
    return {"models": detector_service.catalog(force=True)}


@app.get("/api/detector/colab")
def colab_notebook():
    return FileResponse(ROOT / "gpu_worker" / "V3_LiDAR_Colab.ipynb", filename="V3_LiDAR_Colab.ipynb")


@app.get("/api/detector/bundle")
def detector_bundle():
    payload = BytesIO()
    sources = ["core/lidar_presets.py", "core/lidar_runtime.py", "core/pointcloud.py", "gpu_worker/server.py", "gpu_worker/prepare_models.py", "gpu_worker/verify.py", "gpu_worker/Dockerfile", "gpu_worker/requirements.txt", "gpu_worker/README.md", ".dockerignore"]
    with ZipFile(payload, "w") as archive:
        for source in sources:
            archive.writestr("v3/" + source, (ROOT / source).read_bytes())
    return Response(payload.getvalue(), media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="v3-lidar-worker.zip"'})


@app.post("/api/sessions/{session_id}/guideline")
def apply_guideline(session_id: str, payload: GuidelineRequest):
    try:
        session = store.load(session_id)
        if payload.revision != session["revision"]:
            raise HTTPException(409, "Stale session revision; reload before changing labels")
        if session.get("cvat"):
            raise ValueError("Nhãn phiên CVAT lấy từ job. Hãy dùng job có đúng 10 nhãn của DOCX.")
        canonical = {label.casefold(): label for label in GUIDELINE_LABELS}
        for box in session["boxes"]:
            if box["label"].casefold() not in canonical:
                raise ValueError(f"Box {box['label']} cần được kiểm tra và đổi nhãn trước; không tự ép sang nhãn DOCX.")
            box["label"] = canonical[box["label"].casefold()]
        session["labels"] = list(GUIDELINE_LABELS)
        session["revision"] += 1
        store.save(session)
        return session
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")


@app.post("/api/sessions/upload")
async def upload(request: Request, filename: str):
    data = await request.body()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Point cloud exceeds 200 MB")
    points, colors = parse_pointcloud(data, filename, with_colors=True)
    return store.create(points, Path(filename).name, colors=colors)


@app.post("/api/sessions/demo")
def demo():
    rng = np.random.default_rng(21)
    road = np.column_stack([rng.uniform(-12, 24, 9000), rng.uniform(-10, 10, 9000), rng.normal(-1.6, .025, 9000), np.ones(9000)])
    car = np.column_stack([rng.uniform(5, 9, 1600), rng.uniform(-2, -.1, 1600), rng.uniform(-1.2, .1, 1600), np.ones(1600)])
    other = np.column_stack([rng.uniform(14, 16, 800), rng.uniform(2, 3, 800), rng.uniform(-1.3, .1, 800), np.ones(800)])
    session = store.create(np.vstack([road, car, other]).astype(np.float32), "Demo LiDAR 3D")
    box = Cuboid(id="demo-car", label="car", center=[7, -1, -.55], size=[4, 2, 1.4], source="demo")
    return store.update(session["id"], session["revision"], [box])


class CVATAuth(BaseModel):
    url: str
    username: str
    password: str
    verify_ssl: bool = True

    def connect(self):
        parsed = urlparse(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("CVAT URL must be http or https")
        from cvat_sdk import Config
        from cvat_sdk.core.client import Client
        client = Client(self.url.rstrip("/"), config=Config(verify_ssl=self.verify_ssl))
        client.login((self.username, self.password))
        return client

@app.post("/api/cvat/jobs")
def list_cvat_jobs(auth: CVATAuth):
    try:
        client = auth.connect()
        # Fetch jobs assigned to the user or all accessible jobs
        # cvat_sdk client.jobs.list() returns a list of jobs.
        jobs_data = []
        # List all accessible jobs (first few pages)
        # Note: cvat_sdk list() might return a tuple or object with items
        jobs_response = client.jobs.list()
        # jobs_response is typically an iterable or has .results
        items = getattr(jobs_response, 'results', jobs_response)
        
        # If it's a tuple (which it is in some cvat-sdk versions like (data, response)), extract data
        if isinstance(items, tuple) and len(items) > 0 and isinstance(items[0], (list, tuple)):
            items = items[0]
            
        for job in items[:50]: # Limit to 50 jobs
            # Retrieve project or task info to make it readable
            task_id = job.task_id
            jobs_data.append({
                "id": job.id,
                "task_id": task_id,
                "project_id": getattr(job, 'project_id', None),
                "status": job.state.value if hasattr(job.state, 'value') else str(job.state),
                "stage": job.stage.value if hasattr(job.stage, 'value') else str(job.stage),
                "url": f"{auth.url.rstrip('/')}/tasks/{task_id}/jobs/{job.id}"
            })
        return {"jobs": jobs_data}
    except Exception as error:
        raise HTTPException(400, f"Cannot fetch CVAT jobs: {error}") from error

@app.post("/api/cvat/job")
def job_info(credentials: Credentials):
    try:
        _, job = credentials.connect()
        return {"frames": [{"id": job.start_frame + index, "name": frame.name} for index, frame in enumerate(job.get_frames_info())], "labels": [label.name for label in job.get_labels()]}
    except Exception as error:
        raise HTTPException(400, f"Cannot read CVAT job: {error}") from error


@app.post("/api/sessions/cvat")
def import_job_frame(payload: JobFrame):
    from uuid import uuid4
    from core.geometry import parse_cvat_points
    try:
        _, job = payload.connect()
        frames = job.get_frames_info()
        index = payload.frame - job.start_frame
        if index < 0 or index >= len(frames):
            raise ValueError("Frame is outside this job")
        filename = frames[index].name
        data = job.get_frame(payload.frame, quality="original").read()
        points, colors = parse_pointcloud(data, filename, with_colors=True)
        job_labels = job.get_labels()
        labels = [label.name for label in job_labels]
        session = store.create(points, filename, labels, {"url": payload.url.rstrip("/"), "job_id": payload.job_id, "frame": payload.frame}, colors=colors)
        
        session['label_specs'] = [{'id': label.id, 'name': label.name, 'color': label.color} for label in job_labels]
        session['import_warnings'] = []
        store.save(session)
        # Load existing annotations from CVAT
        try:
            annotations = job.get_annotations()
            label_specs = {label.id: label for label in job.get_labels()}
            labels_by_id = {key: label.name for key, label in label_specs.items()}
            boxes = []
            for shape in annotations.shapes:
                if shape.frame == payload.frame and shape.type.value == "cuboid":
                    label_name = labels_by_id.get(shape.label_id, "Object")
                    label_spec = label_specs[shape.label_id]
                    attribute_names = {spec.id: spec.name for spec in (label_spec.attributes or [])}
                    attributes = {attribute_names[item.spec_id]: item.value for item in (shape.attributes or []) if item.spec_id in attribute_names}
                    try:
                        boxes.append(parse_cvat_points(uuid4().hex, label_name, shape.points, payload.frame, attributes))
                    except (ValueError, TypeError) as error:
                        session['import_warnings'].append(f'Box CVAT {shape.id}: {error}')
                        
            for track in annotations.tracks:
                valid_shapes = [s for s in track.shapes if s.frame <= payload.frame]
                if not valid_shapes:
                    continue
                valid_shapes.sort(key=lambda s: s.frame)
                shape = valid_shapes[-1]
                if shape.outside or shape.type.value != "cuboid":
                    continue
                label_name = labels_by_id.get(track.label_id, "Object")
                label_spec = label_specs[track.label_id]
                attribute_names = {spec.id: spec.name for spec in (label_spec.attributes or [])}
                attributes = {attribute_names[item.spec_id]: item.value for item in (shape.attributes or []) if item.spec_id in attribute_names}
                try:
                    boxes.append(parse_cvat_points(uuid4().hex, label_name, shape.points, payload.frame, attributes))
                except (ValueError, TypeError) as error:
                    session['import_warnings'].append(f'Track CVAT {track.id}: {error}')
            store.save(session)
            if boxes:
                session = store.update(session["id"], session["revision"], boxes)
        except Exception as e:
            session = store.load(session['id'])
            session.setdefault('import_warnings', []).append(f'Không tải được annotation CVAT: {e}')
            store.save(session)

        try:
            _, response = job.api.retrieve_data(job.id, type="context_image", number=payload.frame, _parse_response=False)
            with ZipFile(BytesIO(response.data)) as archive:
                for item in archive.infolist()[:8]:
                    if item.file_size > 15 * 1024 * 1024 or item.is_dir():
                        continue
                    store.add_camera(session["id"], item.filename, archive.read(item))
            session = store.load(session["id"])
        except Exception:
            # A CVAT job may have no related images; point-cloud import still succeeds.
            pass
        return session
    except Exception as error:
        raise HTTPException(400, f"Cannot import 3D frame: {error}") from error


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    try:
        session = store.load(session_id)
        colors = store.colors(session_id)
        return {**session, "points": display_points(store.points(session_id)), 'point_colors': display_points(colors) if colors is not None else None}
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")


@app.post('/api/sessions/{session_id}/boxes/{box_id}/archive')
def archive_box(session_id: str, box_id: str, payload: BoxArchiveRequest):
    try:
        return store.archive_box(session_id, payload.revision, box_id, payload.restore)
    except FileNotFoundError:
        raise HTTPException(404, 'Session not found')
    except ValueError as error:
        raise HTTPException(409 if 'Stale' in str(error) else 400, str(error)) from error


@app.post('/api/sessions/{session_id}/axis-convention')
def set_axis_convention(session_id: str, payload: AxisConventionRequest):
    try:
        return store.set_axis_convention(session_id, payload.revision, payload.convention, payload.apply_existing)
    except FileNotFoundError:
        raise HTTPException(404, 'Session not found')
    except ValueError as error:
        raise HTTPException(409 if 'Stale' in str(error) else 400, str(error)) from error


@app.post("/api/sessions/{session_id}/cameras")
async def add_camera(session_id: str, request: Request, filename: str):
    data = await request.body()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(413, "Camera image exceeds 15 MB")
    try:
        return store.add_camera(session_id, filename, data)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")


@app.get("/api/sessions/{session_id}/cameras/{index}")
def camera_image(session_id: str, index: int):
    try:
        return FileResponse(store.camera_path(session_id, index))
    except (FileNotFoundError, ValueError, IndexError):
        raise HTTPException(404, "Camera image not found")


@app.put("/api/sessions/{session_id}")
def save_session(session_id: str, payload: SaveRequest):
    try:
        return store.update(session_id, payload.revision, payload.boxes)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")
    except ValueError as error:
        raise HTTPException(409 if "Stale" in str(error) else 400, str(error))


@app.post("/api/sessions/{session_id}/detect")
def detect_session(session_id: str, payload: DetectRequest):
    try:
        session = store.load(session_id)
        if payload.revision != session["revision"]:
            raise HTTPException(409, "Stale session revision; reload before inference")
        mapping = default_mapping(session['labels']) if payload.model_id in PRESETS else {name.lower(): name for name in session['labels']}
        mapping.update({source.lower(): target for source, target in payload.label_map.items()})
        if payload.model_id in PRESETS:
            validate_label_map(mapping, session['labels'])
        invalid = set(mapping.values()) - set(session['labels']) - {'__skip__'}
        if invalid:
            raise ValueError(f"Mapped labels do not exist in this job: {', '.join(sorted(invalid))}")
        if not any(value != '__skip__' for value in mapping.values()):
            raise ValueError('Chọn ít nhất một nhãn model để ánh xạ vào job.')
        if any(not np.isfinite(value) or not 0 <= value <= 1 for value in payload.class_thresholds.values()):
            raise ValueError('Ngưỡng theo lớp phải từ 0 đến 1 và hữu hạn.')
        if set(payload.class_thresholds) - set(mapping):
            raise ValueError('Ngưỡng chứa nhãn model không hợp lệ.')
        if payload.profile != 'custom':
            payload.threshold = PROFILES[payload.profile]
            payload.class_thresholds = {}
        inference_threshold = min([payload.threshold, *payload.class_thresholds.values()])
        proposals = detect(store.points(session_id), payload.model_id, inference_threshold, store.bin_path(session_id))
        boxes, report = filter_proposals(proposals, mapping, payload.threshold, payload.class_thresholds)
        boxes = [Cuboid(**{**box.model_dump(), **session.get('axis_convention', AxisConvention().model_dump()), 'frame': (session.get('cvat') or {}).get('frame', 0)}) for box in boxes]
        previous = [Cuboid(**item) for item in session["boxes"]]
        replace = payload.mode == 'replace'
        merged, duplicates = merge_proposals([] if replace else previous, boxes)
        updated = store.update(session_id, session["revision"], merged, archive_existing=replace)
        updated['detection'] = {**report, 'model_id': payload.model_id, 'mode': payload.mode, 'added': len(merged) - (0 if replace else len(previous)), 'replaced': len(previous) if replace else 0, 'duplicates_skipped': duplicates, 'classes_skipped': report['unmapped'] + report['explicit_skip'], 'mapping': mapping, 'class_thresholds': payload.class_thresholds, 'threshold': payload.threshold, 'profile': payload.profile}
        store.save(updated)
        return updated
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")
    except (ValueError, RuntimeError) as error:
        raise HTTPException(409 if "Stale" in str(error) else 400, str(error))


@app.post("/api/sessions/{session_id}/publish")
def publish(session_id: str, payload: PublishRequest):
    if not payload.confirm:
        raise HTTPException(400, "Explicit publish confirmation is required")
    try:
        session = store.load(session_id)
        binding = session.get("cvat")
        if not binding or binding["url"] != payload.url.rstrip("/") or binding["job_id"] != payload.job_id:
            raise ValueError("CVAT connection does not match this session")
        if payload.revision is not None and payload.revision != session['revision']:
            raise HTTPException(409, 'Bản nháp đã thay đổi; tải lại trước khi publish.')
        _, job = payload.connect()
        labels = {label.name: label for label in job.get_labels()}
        published = set(session.get("published_ids", []))
        selected = [Cuboid(**item) for item in session["boxes"] if item["status"] == "accepted" and (payload.mode == 'replace' or (item["id"] not in published and item.get('source') != 'cvat'))]
        if not selected:
            return {"published": 0, "message": "No new accepted cuboids"}
        from cvat_sdk.models import AttributeValRequest, LabeledShapeRequest, PatchedLabeledDataRequest, ShapeType, LabeledTrackRequest, TrackedShapeRequest
        from cvat_sdk.core.proxies.annotations import AnnotationUpdateAction

        tracks = []
        for box in selected:
            exported = cvat_oriented_box(box)
            label = labels.get(box.label)
            if label is None:
                raise ValueError(f"CVAT label missing: {box.label}")
            spec_by_name = {attribute.name: attribute for attribute in (label.attributes or [])}
            attributes = [AttributeValRequest(spec_id=spec_by_name[name].id, value=value) for name, value in axis_attributes(exported).items() if name in spec_by_name]
            
            track_shape = TrackedShapeRequest(
                type=ShapeType("cuboid"),
                frame=binding["frame"],
                points=cvat_points(exported),
                attributes=attributes,
                occluded=False,
                outside=False,
                keyframe=True,
                z_order=0
            )
            tracks.append(LabeledTrackRequest(
                frame=binding["frame"],
                label_id=label.id,
                shapes=[track_shape],
                attributes=[],
                group=0
            ))
            
        replaced = 0
        backup_path = None
        if payload.mode == 'replace':
            from cvat_sdk.models import LabeledDataRequest
            data = job.get_annotations().to_dict()
            if not payload.replacement_token or payload.replacement_token != annotation_token(data):
                raise HTTPException(409, 'Annotation CVAT đã thay đổi hoặc chưa được xem trước. Xem và xác nhận lại danh sách ghi đè.')
            
            previous_shapes = data.get('shapes', [])
            kept_shapes = [shape for shape in previous_shapes if shape['frame'] != binding['frame']]
            
            previous_tracks = data.get('tracks', [])
            for track in previous_tracks:
                track['shapes'] = [s for s in track['shapes'] if s['frame'] != binding['frame']]
            kept_tracks = [t for t in previous_tracks if t['shapes']]
            
            replaced = (len(previous_shapes) - len(kept_shapes)) + (len(previous_tracks) - len(kept_tracks))
            backup_dir = store.root / session_id / 'publish_backups'
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / f'{uuid4().hex}.json'
            with backup_path.open('x', encoding='utf-8') as backup:
                json.dump({'binding': binding, 'annotations': data}, backup, ensure_ascii=False, indent=2)
            replacement = {**data, 'shapes': kept_shapes, 'tracks': [*kept_tracks, *[track.to_dict() for track in tracks]]}
            job.set_annotations(LabeledDataRequest._from_openapi_data(**cvat_replacement_data(replacement)))
        else:
            job.update_annotations(PatchedLabeledDataRequest(tracks=tracks), action=AnnotationUpdateAction.CREATE)
        session["published_ids"] = [box.id for box in selected] if payload.mode == 'replace' else [*published, *[box.id for box in selected]]
        session["revision"] += 1
        store.save(session)
        return {"published": len(selected), "revision": session["revision"], 'mode': payload.mode, 'replaced': replaced, 'backup': str(backup_path) if backup_path else None}
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(400, str(error))


class EvaluationRequest(BaseModel):
    revision: int = Field(ge=0)
    session_ids: list[str] = Field(min_length=1, max_length=20)
    confirmed_complete: bool = False
    label_map: dict[str, str] = Field(default_factory=dict)


@app.get('/api/sessions/{session_id}/evaluation-candidates')
def evaluation_candidates(session_id: str):
    try:
        current=store.load(session_id)
        candidates=[]
        for path in store.root.glob('*.json'):
            if len(path.stem)!=32:continue
            other=store.load(path.stem)
            binding=current.get('cvat') or {}
            other_binding=other.get('cvat') or {}
            same_job=bool(binding) and all(binding.get(key)==other_binding.get(key) for key in ['url','job_id'])
            same_local=not binding and not other_binding and other.get('labels')==current.get('labels')
            count=sum(box.get('status')=='accepted' for box in other['boxes'])
            if count and (same_job or same_local):
                candidates.append({'id':other['id'],'title':other['title'],'accepted':count,'frame':other_binding.get('frame')})
        return {'candidates':candidates}
    except FileNotFoundError:
        raise HTTPException(404,'Session not found')


@app.post('/api/sessions/{session_id}/evaluate')
def evaluate_detector(session_id: str, payload: EvaluationRequest):
    try:
        current=store.load(session_id)
        if payload.revision!=current['revision']:raise HTTPException(409,'Phiên đã thay đổi; tải lại trước khi đánh giá.')
        if not payload.confirmed_complete:raise ValueError('Xác nhận các frame đã gắn đủ vật thể và kiểm tra box chấp nhận.')
        allowed={row['id'] for row in evaluation_candidates(session_id)['candidates']}
        if not set(payload.session_ids)<=allowed:raise ValueError('Chỉ chọn phiên cùng job hoặc cùng bộ nhãn cục bộ đã có box chấp nhận.')
        samples=[];seen=set()
        for id in dict.fromkeys(payload.session_ids):
            sample=store.load(id)
            key=((sample.get('cvat') or {}).get('frame'), (sample.get('cvat') or {}).get('job_id')) if sample.get('cvat') else (id,)
            if key in seen:raise ValueError('Một frame có nhiều bản nháp; chỉ chọn một phiên mỗi frame.')
            seen.add(key)
            samples.append(sample)
        mapping=default_mapping(current['labels']);mapping.update(payload.label_map)
        validate_label_map(mapping,current['labels'])
        if not any(target!='__skip__' for target in mapping.values()):raise ValueError('Không có nhãn nào được ánh xạ.')
        references=[{'id':sample['id'],'revision':sample['revision']} for sample in samples]
        results=[]
        for model_id in PRESETS:
            scores={profile:[] for profile in PROFILES}
            for sample in samples:
                truth=[Cuboid(**box) for box in sample['boxes'] if box['status']=='accepted']
                proposals=detect(store.points(sample['id']),model_id,min(PROFILES.values()),store.bin_path(sample['id']))
                for profile,threshold in PROFILES.items():
                    filtered,_=filter_proposals(proposals,mapping,threshold,{})
                    scores[profile].append(score_predictions(filtered,truth))
            for profile in PROFILES:
                results.append({'model_id':model_id,'profile':profile,'threshold':PROFILES[profile],**aggregate_scores(scores[profile])})
        for reference in references:
            if store.load(reference['id'])['revision']!=reference['revision']:raise HTTPException(409,'Frame mẫu đã thay đổi trong khi đánh giá; chạy lại.')
        results.sort(key=lambda row:(row['f1'],row['precision'],row['recall']),reverse=True)
        report={'metric':'Ghép cùng nhãn, khoảng cách tâm 3D ≤ 2 m; không phải mAP/IoU.', 'samples':references,'mapping':mapping,'results':results,'recommendation':results[0] if results and results[0]['tp'] else None}
        directory=store.root/session_id/'evaluations';directory.mkdir(parents=True,exist_ok=True)
        report_id=uuid4().hex
        with (directory/(report_id+'.json')).open('x',encoding='utf-8') as file:json.dump(report,file,ensure_ascii=False,indent=2)
        return {**report,'report_id':report_id}
    except FileNotFoundError:
        raise HTTPException(404,'Session not found')
    except (ValueError,RuntimeError) as error:
        raise HTTPException(400,str(error))

@app.get('/api/sessions/{session_id}/input-diagnostics')
def input_diagnostics(session_id: str):
    try:
        points=store.points(session_id)
        xyz=points[:,:3]
        ranges=[[float(xyz[:,axis].min()),float(xyz[:,axis].max())] for axis in range(3)]
        fractions={}
        for model_id,spec in PRESETS.items():
            extent=np.asarray(spec['range'])
            fractions[model_id]=float(((xyz>=extent[:3])&(xyz<extent[3:])).all(axis=1).mean())
        summary=f"{len(points):,} điểm. Phạm vi XYZ: {ranges}. Intensity: {float(points[:,3].min()):.3g}–{float(points[:,3].max()):.3g}. "
        summary+=' · '.join(f'{model_id}: {fraction*100:.1f}% điểm trong phạm vi model' for model_id,fraction in fractions.items())
        summary+=' · Kiểm tra đơn vị mét và Z hướng lên; không thể xác nhận chỉ từ min/max. Đổi tên trục trên box không chuyển trục point cloud. PointPillars nuScenes Mac dùng kênh thời gian 0 cho một lượt quét; CenterPoint dùng intensity và thời gian 0. Chưa có kiểm chứng đối chiếu CUDA trên file này.'
        return {'point_count':len(points),'xyz_ranges':ranges,'in_range_fraction':fractions,'summary':summary}
    except FileNotFoundError:
        raise HTTPException(404,'Session not found')

# V4 phase registrations are additive and keep V3 contracts intact.
from api.ground_routes_v4 import install as install_ground_v4
install_ground_v4(app,lambda:store)

from api.camera_routes_v4 import install as install_camera_v4
install_camera_v4(app,lambda:store)

from api.evaluation_routes_v4 import install as install_evaluation_v4
install_evaluation_v4(app,lambda:store)

from api.session_guard_v4 import install as install_session_guard_v4
install_session_guard_v4(app)

from api.backup_routes_v4 import install as install_backup_v4
install_backup_v4(app,lambda:store)

from api.view_snapshot_v4 import install as install_view_snapshot_v4
install_view_snapshot_v4(app,lambda:store)
