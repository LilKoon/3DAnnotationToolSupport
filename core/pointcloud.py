from __future__ import annotations

import io
import numpy as np

MAX_BYTES = 200 * 1024 * 1024
MAX_POINTS_DISPLAY = 100_000


def parse_pointcloud(data: bytes, filename: str, with_colors: bool = False):
    if len(data) > MAX_BYTES:
        raise ValueError("Point cloud exceeds 200 MB")
    colors = None
    suffix = filename.lower().rsplit(".", 1)[-1]
    if suffix == "bin":
        if len(data) % 16:
            raise ValueError("BIN must contain float32 x,y,z,intensity records")
        points = np.frombuffer(data, dtype="<f4").reshape(-1, 4).copy()
    elif suffix == "pcd":
        parsed = _parse_pcd(data, with_colors)
        points, colors = parsed if with_colors else (parsed, None)
    else:
        raise ValueError("Only .pcd and .bin point clouds are supported")
    if not len(points) or not np.isfinite(points).all():
        raise ValueError("Point cloud is empty or contains non-finite values")
    points = points.astype(np.float32, copy=False)
    return (points, colors) if with_colors else points


def _parse_pcd(data: bytes, with_colors: bool = False):
    stream = io.BytesIO(data)
    header: dict[str, list[str]] = {}
    for _ in range(100):
        line = stream.readline()
        if not line:
            raise ValueError("PCD header has no DATA field")
        parts = line.decode("ascii", errors="strict").strip().split()
        if parts and not parts[0].startswith("#"):
            header[parts[0].upper()] = parts[1:]
        if parts and parts[0].upper() == "DATA":
            break
    fields = header.get("FIELDS", [])
    if not {"x", "y", "z"}.issubset(fields):
        raise ValueError("PCD requires x, y, z fields")
    count = int(header.get("POINTS", ["0"])[0])
    if count <= 0 or count > 20_000_000:
        raise ValueError("Invalid PCD POINTS count")
    mode = header.get("DATA", [""])[0].lower()
    if mode == "ascii":
        raw = np.loadtxt(stream, dtype=np.float64, ndmin=2)
        if raw.shape != (count, len(fields)):
            raise ValueError("PCD data does not match header")
        points = _select_fields(raw, fields)
        colors = _point_colors({name: raw[:, index] for index, name in enumerate(fields)}, fields, header.get('TYPE', [])) if with_colors else None
        return (points, colors) if with_colors else points
    if mode != "binary":
        raise ValueError("PCD DATA must be ascii or uncompressed binary")
    sizes = [int(v) for v in header.get("SIZE", [])]
    types = header.get("TYPE", [])
    counts = [int(v) for v in header.get("COUNT", ["1"] * len(fields))]
    if len(sizes) != len(fields) or len(types) != len(fields) or len(counts) != len(fields):
        raise ValueError("PCD binary field metadata is incomplete")
    codes = {("F", 4): "<f4", ("F", 8): "<f8", ("I", 1): "i1", ("I", 2): "<i2", ("I", 4): "<i4", ("U", 1): "u1", ("U", 2): "<u2", ("U", 4): "<u4"}
    try:
        dtype = np.dtype([(name, codes[(kind, size)], (n,) if n > 1 else ()) for name, size, kind, n in zip(fields, sizes, types, counts)])
    except KeyError as error:
        raise ValueError(f"Unsupported PCD field type: {error}") from error
    payload = stream.read()
    if len(payload) != count * dtype.itemsize:
        raise ValueError("PCD binary data does not match header")
    records = np.frombuffer(payload, dtype=dtype, count=count)
    points = np.column_stack([records[name] for name in ("x", "y", "z", "intensity") if name in fields] + ([] if "intensity" in fields else [np.zeros(count)]))
    colors = _point_colors(records, fields, types) if with_colors else None
    return (points, colors) if with_colors else points


def _select_fields(raw: np.ndarray, fields: list[str]) -> np.ndarray:
    columns = [raw[:, fields.index(name)] for name in ("x", "y", "z")]
    columns.append(raw[:, fields.index("intensity")] if "intensity" in fields else np.zeros(len(raw)))
    return np.column_stack(columns)


def display_points(points: np.ndarray) -> list[list[float]]:
    stride = max(1, int(np.ceil(len(points) / MAX_POINTS_DISPLAY)))
    return points[::stride].round(3).tolist()


def _point_colors(records, fields, types):
    if {'r', 'g', 'b'}.issubset(fields):
        rgb = np.column_stack([records[name] for name in ('r','g','b')])
        if not np.isfinite(rgb).all() or (rgb < 0).any() or (rgb > 255).any():
            raise ValueError('PCD RGB channels must be finite and between 0 and 255')
        return rgb.astype(np.uint8)
    name = 'rgb' if 'rgb' in fields else 'rgba' if 'rgba' in fields else None
    if name is None:
        return None
    values = np.asarray(records[name])
    if len(types) != len(fields):
        raise ValueError('PCD RGB requires TYPE metadata')
    if types[fields.index(name)] == 'F':
        packed = values.astype('<f4').view('<u4')
    else:
        if not np.isfinite(values).all() or (values < 0).any() or (values > 0xffffffff).any():
            raise ValueError('Invalid packed PCD RGB')
        packed = values.astype(np.uint32)
    return np.column_stack([(packed >> 16) & 255, (packed >> 8) & 255, packed & 255]).astype(np.uint8)
