from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4
import numpy as np
from io import BytesIO
from PIL import Image

from .geometry import Cuboid, AxisConvention
from .lidar_presets import GUIDELINE_LABELS


class SessionStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        if len(session_id) != 32 or any(char not in "0123456789abcdef" for char in session_id):
            raise ValueError("Invalid session ID")
        return self.root / f"{session_id}.json"

    def create(self, points: np.ndarray, title: str, labels: list[str] | None = None, cvat: dict | None = None, colors: np.ndarray | None = None) -> dict:
        session_id = uuid4().hex
        point_path = self.root / f"{session_id}.npy"
        if colors is not None:
            colors = np.asarray(colors)
            if colors.shape != (len(points), 3) or not np.isfinite(colors).all() or (colors < 0).any() or (colors > 255).any():
                raise ValueError('Point colors must be Nx3 RGB bytes')
            np.save(self.root / f'{session_id}.colors.npy', colors.astype(np.uint8), allow_pickle=False)
        np.save(point_path, points, allow_pickle=False)
        points.astype("<f4", copy=False).tofile(self.root / f"{session_id}.bin")
        session = {"id": session_id, "title": title, "labels": labels or list(GUIDELINE_LABELS), "cvat": cvat, "revision": 0, "boxes": [], "cameras": [], 'axis_convention': AxisConvention().model_dump()}
        self.save(session)
        return session

    def load(self, session_id: str) -> dict:
        session = json.loads(self._path(session_id).read_text(encoding="utf-8"))
        session.setdefault('axis_convention', AxisConvention().model_dump())
        return session

    def points(self, session_id: str) -> np.ndarray:
        self._path(session_id)  # validate ID
        return np.load(self.root / f"{session_id}.npy", allow_pickle=False)

    def colors(self, session_id: str):
        self._path(session_id)
        path = self.root / f'{session_id}.colors.npy'
        return np.load(path, allow_pickle=False) if path.exists() else None

    def bin_path(self, session_id: str) -> Path:
        self._path(session_id)  # validate ID
        return self.root / f"{session_id}.bin"

    def add_camera(self, session_id: str, filename: str, data: bytes) -> dict:
        if len(data) > 15 * 1024 * 1024:
            raise ValueError("Camera image exceeds 15 MB")
        image = Image.open(BytesIO(data))
        if image.format not in {"JPEG", "PNG", "WEBP"}:
            raise ValueError("Camera image must be JPEG, PNG or WebP")
        if image.width * image.height > 40_000_000:
            raise ValueError("Camera image exceeds 40 megapixels")
        image.verify()
        session = self.load(session_id)
        session.setdefault("cameras", [])
        index = len(session["cameras"])
        if index >= 8:
            raise ValueError("Maximum 8 camera images per frame")
        extension = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}[image.format]
        directory = self.root / session_id / "cameras"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{index}{extension}"
        path.write_bytes(data)
        session["cameras"].append({"name": Path(filename).name, "index": index})
        session["revision"] += 1
        self.save(session)
        return session

    def camera_path(self, session_id: str, index: int) -> Path:
        session = self.load(session_id)
        if index < 0 or index >= len(session.get("cameras", [])):
            raise IndexError("Camera index out of range")
        for extension in (".jpg", ".png", ".webp"):
            path = self.root / session_id / "cameras" / f"{index}{extension}"
            if path.is_file():
                return path
        raise FileNotFoundError("Camera image not found")

    def save(self, session: dict) -> None:
        path = self._path(session["id"])
        payload = json.dumps(session, ensure_ascii=False, indent=2)
        # Existing revisions remain recoverable in a sibling history directory.
        if path.exists():
            previous = json.loads(path.read_text(encoding="utf-8"))
            history = self.root / session["id"]
            history.mkdir(exist_ok=True)
            backup = history / f"{previous['revision']:08d}.json"
            if not backup.exists():
                backup.write_text(json.dumps(previous, ensure_ascii=False, indent=2), encoding="utf-8")
        path.write_text(payload, encoding="utf-8")

    def update(self, session_id: str, revision: int, boxes: list[Cuboid], archive_existing: bool = False) -> dict:
        session = self.load(session_id)
        if revision != session["revision"]:
            raise ValueError("Stale session revision; reload before saving")
        ids = [box.id for box in boxes]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate cuboid IDs")
        if session.get("cvat"):
            allowed = set(session["labels"])
            if any(box.label not in allowed for box in boxes):
                raise ValueError("Cuboid label does not exist in CVAT job")
        if archive_existing:
            archived = session.setdefault('deleted_boxes', [])
            occupied = {box['id'] for box in archived} | set(ids)
            for old in session['boxes']:
                preserved = dict(old)
                if preserved['id'] in occupied:
                    preserved['id'] = uuid4().hex
                occupied.add(preserved['id'])
                archived.append(preserved)
        session["boxes"] = [box.model_dump() for box in boxes]
        session["revision"] += 1
        self.save(session)
        return session

    def archive_box(self, session_id: str, revision: int, box_id: str, restore: bool = False) -> dict:
        """Hide a box reversibly. Preserve its complete geometry and metadata."""
        session = self.load(session_id)
        if revision != session['revision']:
            raise ValueError('Stale session revision; reload before saving')
        archived = session.setdefault('deleted_boxes', [])
        source = archived if restore else session['boxes']
        target = session['boxes'] if restore else archived
        matches = [box for box in source if box['id'] == box_id]
        if len(matches) != 1:
            raise ValueError('Box không tồn tại trong danh sách hiện tại.')
        if any(box['id'] == box_id for box in target):
            raise ValueError('Box ID đã tồn tại trong danh sách đích.')
        target.append(matches[0])
        source[:] = [box for box in source if box['id'] != box_id]
        session['revision'] += 1
        self.save(session)
        return session

    def set_axis_convention(self, session_id: str, revision: int, convention: AxisConvention, apply_existing: bool = False) -> dict:
        session = self.load(session_id)
        if session['revision'] != revision:
            raise ValueError('Stale session revision; reload before saving')
        session['axis_convention'] = convention.model_dump()
        if apply_existing:
            for box in session['boxes']:
                box.update(convention.model_dump())
        session['revision'] += 1
        self.save(session)
        return session
