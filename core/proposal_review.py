"""Merge new suggestions without replacing an annotator's existing cuboids."""
import math
import numpy as np
from .geometry import Cuboid


def footprint(box: Cuboid) -> np.ndarray:
    c, s = math.cos(box.yaw), math.sin(box.yaw)
    rotation = np.array([[c, -s], [s, c]])
    half = np.asarray(box.size[:2]) / 2
    return np.asarray([[-1, -1], [1, -1], [1, 1], [-1, 1]]) * half @ rotation.T + box.center[:2]


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def cuboid_iou(a: Cuboid, b: Cuboid) -> float:
    """Yaw-aware 3D IoU, using convex polygon clipping for XY overlap."""
    z_overlap = min(a.center[2] + a.size[2]/2, b.center[2] + b.size[2]/2) - max(a.center[2] - a.size[2]/2, b.center[2] - b.size[2]/2)
    if z_overlap <= 0:
        return 0.0
    polygon = list(footprint(a))
    clip = footprint(b)
    for index, edge_start in enumerate(clip):
        edge_end = clip[(index + 1) % 4]
        edge = edge_end - edge_start
        source, polygon = polygon, []
        if not source:
            return 0.0
        previous = source[-1]
        previous_distance = cross(edge, previous - edge_start)
        for current in source:
            current_distance = cross(edge, current - edge_start)
            inside, was_inside = current_distance >= -1e-9, previous_distance >= -1e-9
            if inside != was_inside:
                ratio = previous_distance / (previous_distance - current_distance)
                polygon.append(previous + ratio * (current - previous))
            if inside:
                polygon.append(current)
            previous, previous_distance = current, current_distance
    if len(polygon) < 3:
        return 0.0
    area = abs(sum(cross(polygon[i], polygon[(i+1) % len(polygon)]) for i in range(len(polygon)))) / 2
    intersection = area * z_overlap
    union = np.prod(a.size) + np.prod(b.size) - intersection
    return float(intersection / union) if union > 0 else 0.0


def merge_proposals(existing: list[Cuboid], proposals: list[Cuboid]) -> tuple[list[Cuboid], int]:
    result, skipped = list(existing), 0
    for proposal in proposals:
        duplicate = False
        for box in result:
            # Preserve corrected labels from a previous run of the same model.
            if box.label.casefold() != proposal.label.casefold() and box.source != proposal.source:
                continue
            if np.linalg.norm(np.array(box.center[:2]) - proposal.center[:2]) > max(box.size[0], box.size[1], proposal.size[0], proposal.size[1]):
                continue
            if cuboid_iou(box, proposal) >= 0.5:
                duplicate = True
                break
        if duplicate:
            skipped += 1
        else:
            result.append(proposal)
    return result, skipped
