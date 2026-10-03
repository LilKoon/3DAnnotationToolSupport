from __future__ import annotations

import math
from pydantic import BaseModel, Field, field_validator


class AxisConvention(BaseModel):
    """Object X/Y/Z mapped to cuboid length/width/height axes, then signed."""
    axis_order: list[int] = Field(default_factory=lambda: [0, 1, 2], min_length=3, max_length=3)
    axis_signs: list[int] = Field(default_factory=lambda: [1, 1, 1], min_length=3, max_length=3)

    @field_validator('axis_order')
    @classmethod
    def valid_order(cls, values: list[int]) -> list[int]:
        if sorted(values) != [0, 1, 2]:
            raise ValueError('Axis order must be a permutation of 0, 1, 2')
        return values

    @field_validator('axis_signs')
    @classmethod
    def valid_signs(cls, values: list[int]) -> list[int]:
        if any(value not in (-1, 1) for value in values):
            raise ValueError('Axis signs must be +1 or -1')
        return values


class Cuboid(AxisConvention):
    id: str
    frame: int = 0
    label: str
    center: list[float] = Field(min_length=3, max_length=3)
    size: list[float] = Field(min_length=3, max_length=3)
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0
    confidence: float | None = None
    source: str = "manual"
    status: str = "pending"

    @field_validator("center", "size")
    @classmethod
    def finite_vector(cls, values: list[float]) -> list[float]:
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Coordinates must be finite")
        return values

    @field_validator("size")
    @classmethod
    def positive_size(cls, values: list[float]) -> list[float]:
        if any(value <= 0 for value in values):
            raise ValueError("Box dimensions must be positive")
        return values

    @field_validator("yaw", "pitch", "roll")
    @classmethod
    def finite_yaw(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Yaw must be finite")
        return value

    @field_validator("status")
    @classmethod
    def valid_status(cls, value: str) -> str:
        if value not in {"pending", "accepted", "rejected"}:
            raise ValueError("Invalid review status")
        return value


def rotation_matrix(roll, pitch, yaw, order='ZYX'):
    import numpy as np
    cr, sr, cp, sp, cy, sy = math.cos(roll), math.sin(roll), math.cos(pitch), math.sin(pitch), math.cos(yaw), math.sin(yaw)
    rx = np.array([[1,0,0],[0,cr,-sr],[0,sr,cr]])
    ry = np.array([[cp,0,sp],[0,1,0],[-sp,0,cp]])
    rz = np.array([[cy,-sy,0],[sy,cy,0],[0,0,1]])
    return rx @ ry @ rz if order == 'XYZ' else rz @ ry @ rx


def euler_angles(matrix, order='ZYX'):
    import numpy as np
    if order == 'XYZ':
        pitch = math.asin(float(np.clip(matrix[0,2],-1,1)))
        if abs(math.cos(pitch)) < 1e-7:
            return math.atan2(matrix[2,1],matrix[1,1]),pitch,0.0
        return math.atan2(-matrix[1,2],matrix[2,2]),pitch,math.atan2(-matrix[0,1],matrix[0,0])
    pitch = math.asin(float(np.clip(-matrix[2,0],-1,1)))
    if abs(math.cos(pitch)) < 1e-7:
        return 0.0,pitch,math.atan2(-matrix[0,1],matrix[1,1])
    return math.atan2(matrix[2,1],matrix[2,2]),pitch,math.atan2(matrix[1,0],matrix[0,0])


def cvat_points(box: Cuboid) -> list[float]:
    """CVAT 3D cuboid: position, Euler rotation, scale, projection placeholders."""
    rotation = euler_angles(rotation_matrix(box.roll, box.pitch, box.yaw), 'XYZ')
    return [*box.center, *rotation, *box.size, *([0.0] * 7)]


def axis_attributes(box: Cuboid) -> dict[str, str]:
    return {'axis_order': ','.join('XYZ'[i] for i in box.axis_order), **{f'axis_{axis}': str(sign) for axis, sign in zip('xyz', box.axis_signs)}}


def cvat_oriented_box(box: Cuboid) -> Cuboid:
    """Bake object-axis mapping into a proper rotation, preserving all corners."""
    import numpy as np
    cr, sr = math.cos(box.roll), math.sin(box.roll)
    cp, sp = math.cos(box.pitch), math.sin(box.pitch)
    cy, sy = math.cos(box.yaw), math.sin(box.yaw)
    rotation = np.array([[cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr],
                         [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr],
                         [-sp, cp*sr, cp*cr]])
    mapped = rotation[:, box.axis_order] * np.asarray(box.axis_signs)
    if np.linalg.det(mapped) < 0:
        raise ValueError(f'Box {box.label} (ID {box.id}) có hệ trục tay trái. CVAT chỉ hỗ trợ hệ trục tay phải; đảo thêm một trục X/Y/Z trong tool rồi publish lại.')
    pitch = math.asin(float(np.clip(-mapped[2, 0], -1, 1)))
    if abs(math.cos(pitch)) < 1e-7:
        roll, yaw = 0.0, math.atan2(-mapped[0, 1], mapped[1, 1])
    else:
        roll, yaw = math.atan2(mapped[2, 1], mapped[2, 2]), math.atan2(mapped[1, 0], mapped[0, 0])
    return Cuboid(**{**box.model_dump(), 'roll': roll, 'pitch': pitch, 'yaw': yaw,
                     'size': [box.size[i] for i in box.axis_order], 'axis_order': [0, 1, 2], 'axis_signs': [1, 1, 1]})


def parse_cvat_points(id: str, label: str, points: list[float], frame: int, attributes: dict[str, str] | None = None) -> Cuboid:
    """Parse CVAT 3D cuboid from points array."""
    x, y, z = points[0:3]
    roll, pitch, yaw = euler_angles(rotation_matrix(*points[3:6], order='XYZ'))
    dx, dy, dz = points[6:9]
    attributes = attributes or {}
    convention = AxisConvention(axis_order=['XYZ'.index(token.strip().upper()) for token in attributes.get('axis_order', 'X,Y,Z').split(',')], axis_signs=[int(attributes.get(f'axis_{axis}', '1')) for axis in 'xyz'])
    return Cuboid(
        **convention.model_dump(),
        id=id,
        frame=frame,
        label=label,
        center=[x, y, z],
        size=[dx, dy, dz],
        yaw=yaw,
        roll=roll,
        pitch=pitch,
        source="cvat",
        status="accepted" # Already accepted on CVAT
    )
