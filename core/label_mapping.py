"""Job-specific label mapping and auditable proposal filtering."""
from collections import Counter
from .lidar_presets import GUIDELINE_LABELS
from .geometry import Cuboid

def default_mapping(labels):
    names = {name.casefold(): name for name in labels}
    grouped = {'car': ('vehicles', 'vehicle'), 'motorcycle': ('two-wheels',), 'bicycle': ('two-wheels',)}
    return {source: names.get(source, next((names[name] for name in grouped.get(source, ()) if name in names), '__skip__')) for source in GUIDELINE_LABELS}

def filter_proposals(proposals, mapping, threshold, class_thresholds):
    counts = Counter()
    by_class = {}
    boxes = []
    for box in proposals:
        source = box.label.lower()
        row = by_class.setdefault(source, {'returned': 0, 'mapped': 0, 'below_threshold': 0, 'explicit_skip': 0, 'unmapped': 0})
        row['returned'] += 1
        target = mapping.get(source)
        reason = 'unmapped' if target is None else 'explicit_skip' if target == '__skip__' else 'below_threshold' if box.confidence is not None and box.confidence < class_thresholds.get(source, threshold) else 'mapped'
        row[reason] += 1
        counts[reason] += 1
        if reason == 'mapped':
            boxes.append(Cuboid(**{**box.model_dump(), 'label': target}))
    return boxes, {'returned': len(proposals), 'by_class': by_class, **{key: counts[key] for key in ['mapped', 'below_threshold', 'explicit_skip', 'unmapped']}}
