import math

def normalize_angle(a):
    while a > 180: a -= 360
    while a <= -180: a += 360
    return a

def associate_by_topology(boxes, detections, mapping, fov):
    rows = []
    fov_centers = {
        'cam-f': 0, 'cam-fl': 60, 'cam-bl': 120,
        'cam-b': 180, 'cam-br': -120, 'cam-fr': -60
    }
    
    fov_boxes = []
    for b in boxes:
        if b.status == 'rejected': continue
        yaw = math.degrees(math.atan2(b.center[1], b.center[0]))
        diff = normalize_angle(yaw - fov_centers.get(fov, 0))
        if abs(diff) <= 35:  # ~70 degree FOV
            fov_boxes.append((b, diff))
            
    # Sort boxes left-to-right (diff descending)
    fov_boxes.sort(key=lambda x: x[1], reverse=True)

    boxes_by_label = {}
    for b, _ in fov_boxes:
        boxes_by_label.setdefault(b.label, []).append(b)

    # Sort detections left-to-right (bbox[0] ascending)
    detections = sorted(detections, key=lambda d: d['bbox'][0])
    
    used_boxes = set()
    for d in detections:
        row={'detection_id':d['id'],'label':d['label'],'bbox':d['bbox'],'confidence':d.get('confidence'),'box_id':None,'status':'reference_only','evidence':'topology'}
        target = mapping.get(d['label'])
        if target:
            target_boxes = boxes_by_label.get(target, [])
            matched = next((b for b in target_boxes if b.id not in used_boxes), None)
            if matched:
                used_boxes.add(matched.id)
                row.update(box_id=matched.id, status='matched', overlap=0.99)
            else:
                row['status'] = 'unmatched'
        else:
            row['status'] = 'unsupported_label'
        rows.append(row)
    return rows
