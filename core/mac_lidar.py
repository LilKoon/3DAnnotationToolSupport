"""Inference-only pillar networks on PyTorch MPS, without MMCV/CUDA extensions.

Architecture and box conventions follow the configs embedded in the verified
OpenMMLab checkpoints. Source: mmdetection3d models at tag v1.4.0 and
https://docs.pytorch.org/docs/2.14/notes/mps.html . No checkpoint config is executed.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
import threading

import numpy as np

from .lidar_presets import PRESETS, GUIDELINE_LABELS, model_points
from .geometry import Cuboid
from .proposal_review import cuboid_iou

HASHES = {
    'pointpillars-nuscenes': 'fca299c162adb38c1094cb8cdd15315d53f3cd333646b7a8531e29d7ced97dbf',
    'centerpoint-nuscenes': '191a38226d2ce990f26cc3f78c454310cc562d81d29e86d8ca8fa39c0a44215d',
}


def mac_model_points(points, model_id, intensity_scale=1.0):
    prepared = model_points(points, model_id, intensity_scale)
    if model_id == 'pointpillars-nuscenes':
        # Source: v0.16.0/datasets/pipelines/loading.py, MultiSweeps use_dim.
        prepared[:, 3] = 0  # XYZ + key-frame time lag, not reflectance.
    return prepared


def pillars(points, model_id, max_voxels=40000):
    """Deterministic hard voxelization: first points and first occupied cells win."""
    cp = model_id == 'centerpoint-nuscenes'
    step, cap = (.2, 20) if cp else (.25, 64)
    lower = np.asarray(PRESETS[model_id]['range'][:3], dtype=np.float32)
    grid = np.floor((points[:, :3] - lower) / [step, step, 8]).astype(np.int32)
    width = 512 if cp else 400
    valid = ((grid >= 0) & (grid < [width, width, 1])).all(axis=1)
    grid, points = grid[valid], points[valid]
    if not len(points):
        raise ValueError('Không có điểm trong vùng pillar của model.')
    cells, first, inverse = np.unique(grid[:, 1] * width + grid[:, 0], return_index=True, return_inverse=True)
    order = np.argsort(first)[:max_voxels]
    remap = np.full(len(cells), -1, dtype=np.int32)
    remap[order] = np.arange(len(order))
    ids = remap[inverse]
    voxels = np.zeros((len(order), cap, points.shape[1]), dtype=np.float32)
    counts = np.zeros(len(order), dtype=np.int32)
    for point, cell in zip(points, ids):
        if cell >= 0 and counts[cell] < cap:
            voxels[cell, counts[cell]] = point
            counts[cell] += 1
    coords = grid[first[order]]
    cluster = voxels[:, :, :3] - voxels[:, :, :3].sum(axis=1, keepdims=True) / counts[:, None, None]
    centers = coords * [step, step, 8] + lower + [step / 2, step / 2, 4]
    offset = voxels[:, :, :3] - centers[:, None]
    decorated = np.concatenate([voxels, cluster, offset], axis=2).astype(np.float32)
    decorated *= (np.arange(cap)[None, :] < counts[:, None])[:, :, None]
    return decorated, coords, counts


def anchors(height, width, scale):
    sizes = np.asarray([[2.5981, .866, 1], [1.7321, .5774, 1], [1, 1, 1], [.4, .4, 1]], dtype=np.float32) * scale
    out = np.zeros((height, width, 4, 2, 7), dtype=np.float32)
    out[..., 0] = (-50 + (np.arange(width) + .5) * 100 / width)[None, :, None, None]
    out[..., 1] = (-50 + (np.arange(height) + .5) * 100 / height)[:, None, None, None]
    out[..., 2] = -1.8
    out[..., 3:6] = sizes[None, None, :, None, :]
    out[..., 6] = [0, 1.57]
    return out.reshape(-1, 7)


def decode_deltas(priors, deltas, directions):
    result = np.empty((len(priors), 7), dtype=np.float32)
    diagonal = np.linalg.norm(priors[:, 3:5], axis=1)
    result[:, :2] = priors[:, :2] + deltas[:, :2] * diagonal[:, None]
    # Return geometric center directly; the original decoder returns bottom z.
    result[:, 2] = priors[:, 2] + priors[:, 5] / 2 + deltas[:, 2] * priors[:, 5]
    result[:, 3:6] = priors[:, 3:6] * np.exp(deltas[:, 3:6])
    yaw = priors[:, 6] + deltas[:, 6] - (-.7854)
    result[:, 6] = yaw - np.floor(yaw / math.pi) * math.pi - .7854 + math.pi * directions
    return result


def bev_iou(a, b):
    # Equal unit height makes the existing polygon clipper compute BEV IoU.
    return cuboid_iou(Cuboid(id='a', label='car', center=[*a[:2], 0], size=[*a[3:5], 1], yaw=float(a[6])),
                      Cuboid(id='b', label='car', center=[*b[:2], 0], size=[*b[3:5], 1], yaw=float(b[6])))


def suppress(boxes, scores, threshold=.2, circle=None, limit=500):
    order, keep = np.argsort(-scores, kind='stable'), []
    while len(order) and len(keep) < limit:
        current, remaining = order[0], order[1:]
        keep.append(int(current))
        delta = boxes[remaining, :2] - boxes[current, :2]
        if circle is not None:
            # OpenMMLab circle_nms compares squared distance to min_radius.
            order = remaining[(delta * delta).sum(axis=1) > circle]
        else:
            radii = np.linalg.norm(boxes[remaining, 3:5], axis=1)/2 + np.linalg.norm(boxes[current, 3:5])/2
            nearby = (delta * delta).sum(axis=1) <= radii * radii
            reject = np.zeros(len(remaining), dtype=bool)
            for position in np.flatnonzero(nearby):
                reject[position] = bev_iou(boxes[current], boxes[remaining[position]]) > threshold
            order = remaining[~reject]
    return keep


class PillarNetwork:
    """Functional inference graph consuming every checkpoint tensor explicitly."""
    def __init__(self, checkpoint, model_id, device):
        import torch
        self.torch = torch
        self.F = torch.nn.functional
        loaded = torch.load(checkpoint, map_location='cpu', weights_only=True)
        self.classes = list(loaded['meta']['CLASSES'])
        if len(self.classes) != 10 or set(self.classes) != set(GUIDELINE_LABELS):
            raise ValueError('Checkpoint không có đúng 10 nhãn DOCX.')
        self.weights = {key: value.to(device) for key, value in loaded['state_dict'].items()}
        self.used = set()
        self.cp = model_id == 'centerpoint-nuscenes'
        self.device, self.model_id = device, model_id

    def w(self, key):
        self.used.add(key)
        return self.weights[key]

    def conv(self, x, name, stride=1, transpose=False):
        weight = self.w(name + '.weight')
        bias = self.w(name + '.bias') if name + '.bias' in self.weights else None
        if transpose:
            return self.F.conv_transpose2d(x, weight, bias, stride=stride)
        return self.F.conv2d(x, weight, bias, stride=stride, padding=(weight.shape[-1] // 2 if weight.shape[-1] % 2 else 0))

    def norm(self, x, name, eps=.001):
        return self.F.batch_norm(x, self.w(name+'.running_mean'), self.w(name+'.running_var'), self.w(name+'.weight'), self.w(name+'.bias'), training=False, eps=eps)

    def module(self, x, name, eps=.001):
        return self.F.relu(self.norm(self.conv(x, name+'.conv'), name+'.bn', eps))

    def forward(self, decorated, coords):
        t, F = self.torch, self.F
        features = []
        # Chunking bounds pillar encoder memory without changing max pooling.
        for start in range(0, len(decorated), 2048):
            x = t.from_numpy(decorated[start:start+2048]).to(self.device)
            layers = ['pfn_layers.0'] if self.cp else ['vfe_layers.0', 'vfe_layers.1']
            for index, layer in enumerate(layers):
                prefix = 'pts_voxel_encoder.' + layer
                x = F.linear(x, self.w(prefix+'.linear.weight'))
                x = F.relu(self.norm(x.transpose(1,2).contiguous(), prefix+'.norm').transpose(1,2))
                maximum = x.max(dim=1, keepdim=True).values
                x = t.cat([x, maximum.expand(-1,x.shape[1],-1)], dim=2) if index < len(layers)-1 else maximum[:,0]
            features.append(x)
        encoded = t.cat(features)
        width = 512 if self.cp else 400
        canvas = t.zeros((64, width*width), device=self.device)
        indices = t.from_numpy((coords[:,1]*width + coords[:,0]).astype(np.int64)).to(self.device)
        canvas[:,indices] = encoded.T
        x, stages = canvas.view(1,64,width,width), []
        for stage, count in enumerate([4,6,6]):
            for layer in range(count):
                prefix = f'pts_backbone.blocks.{stage}.'
                x = F.relu(self.norm(self.conv(x,prefix+str(layer*3),stride=2 if layer==0 else 1),prefix+str(layer*3+1)))
            stages.append(x)
        if self.cp:
            up = []
            for index, stride in enumerate([2,1,2]):
                prefix = f'pts_neck.deblocks.{index}.'
                up.append(F.relu(self.norm(self.conv(stages[index],prefix+'0',stride,index==2),prefix+'1')))
            x = self.module(t.cat(up,dim=1),'pts_bbox_head.shared_conv',eps=1e-5)
            heads = []
            for task in range(6):
                outputs = {}
                for head in ['reg','height','dim','rot','vel','heatmap']:
                    prefix = f'pts_bbox_head.task_heads.{task}.{head}'
                    outputs[head] = self.conv(self.module(x,prefix+'.0',eps=1e-5),prefix+'.1')[0].cpu().numpy()
                heads.append(outputs)
        else:
            lateral = [self.module(stage,f'pts_neck.lateral_convs.{i}') for i,stage in enumerate(stages)]
            for i in [2,1]:
                lateral[i-1] = lateral[i-1] + F.interpolate(lateral[i],size=lateral[i-1].shape[-2:],mode='nearest')
            heads = []
            for i,x in enumerate(lateral):
                x = self.module(x,f'pts_neck.fpn_convs.{i}')
                heads.append({name:self.conv(x,'pts_bbox_head.'+name)[0].cpu().numpy() for name in ['conv_cls','conv_reg','conv_dir_cls']})
        unused = set(self.weights) - self.used
        unused = {key for key in unused if not key.endswith('.num_batches_tracked')}
        if unused:
            raise RuntimeError('Checkpoint chứa tensor chưa được xử lý: '+str(sorted(unused)))
        return heads

    def decode(self, heads, threshold):
        candidates = []
        if self.cp:
            offset = 0
            for task, head in enumerate(heads):
                heat = 1 / (1 + np.exp(-np.clip(head['heatmap'], -80, 80)))
                classes, height, width = heat.shape
                # Top 500 over all classes equals per-class top500 then global500.
                flat = heat.ravel()
                top = np.argsort(-flat,kind='stable')[:500]
                scores = flat[top]
                spatial = top % (height*width)
                labels = top // (height*width) + offset
                gather = lambda key: head[key].reshape(head[key].shape[0],-1)[:,spatial].T
                reg, rot = gather('reg'), gather('rot')
                boxes = np.column_stack([(spatial%width+reg[:,0])*.8-51.2,(spatial//width+reg[:,1])*.8-51.2,gather('height')[:,0],np.exp(gather('dim')),np.arctan2(rot[:,0],rot[:,1])])
                valid = (scores > max(.1,threshold)) & np.isfinite(boxes).all(axis=1) & (boxes[:,3:6]>0).all(axis=1) & (boxes[:,:3]>=[-61.2,-61.2,-10]).all(axis=1) & (boxes[:,:3]<=[61.2,61.2,10]).all(axis=1)
                boxes,scores,labels = boxes[valid],scores[valid],labels[valid]
                for i in suppress(boxes,scores,circle=[4,12,10,1,.85,.175][task],limit=83):
                    candidates.append((boxes[i],float(scores[i]),int(labels[i])))
                offset += classes
        else:
            all_boxes, all_scores = [], []
            for level,head in enumerate(heads):
                score = head['conv_cls'].transpose(1,2,0).reshape(-1,10)
                score = 1/(1+np.exp(-np.clip(score,-80,80)))
                delta = head['conv_reg'].transpose(1,2,0).reshape(-1,9)
                direction = head['conv_dir_cls'].transpose(1,2,0).reshape(-1,2).argmax(axis=1)
                prior = anchors(*head['conv_cls'].shape[-2:],2**level)
                top = np.argsort(-score.max(axis=1),kind='stable')[:1000]
                all_boxes.append(decode_deltas(prior[top],delta[top],direction[top]))
                all_scores.append(score[top])
            boxes,scores = np.concatenate(all_boxes),np.concatenate(all_scores)
            finite = np.isfinite(boxes).all(axis=1) & (boxes[:,3:6]>0).all(axis=1)
            for label in range(10):
                valid = finite & (scores[:,label] > max(.05,threshold))
                b,s = boxes[valid],scores[valid,label]
                for i in suppress(b,s):
                    candidates.append((b[i],float(s[i]),label))
        candidates.sort(key=lambda item:-item[1])
        return [{'label':self.classes[label],'center':box[:3].tolist(),'size':box[3:6].tolist(),'yaw':float((box[6]+math.pi)%(2*math.pi)-math.pi),'confidence':score} for box,score,label in candidates[:500]]


class MacLidarRuntime:
    def __init__(self, weights_root=None):
        self.root = Path(weights_root) if weights_root else Path(__file__).resolve().parents[1]/'mac_models/checkpoints'
        self.lock = threading.Lock()
        self.models = {}
        self.verified = {}
        self.errors = {}

    def path(self, model_id):
        return self.root / PRESETS[model_id]['checkpoint'].split('/')[-1]

    def load(self, model_id, device):
        key = (model_id,device)
        if key not in self.models:
            path = self.path(model_id)
            if hashlib.sha256(path.read_bytes()).hexdigest() != HASHES[model_id]:
                raise ValueError('Checkpoint hỏng hoặc không khớp bản chính thức: '+path.name)
            self.models[key] = PillarNetwork(path,model_id,device)
        return self.models[key]

    def status(self):
        try:
            import torch
            available = torch.backends.mps.is_available()
            error = None if available else 'Metal/MPS chưa khả dụng. Chạy ./run.sh trực tiếp trong Terminal trên Mac.'
        except ImportError:
            available, error = False, 'Cài PyTorch trong môi trường chạy V3 để dùng GPU Mac.'
        result = []
        for model_id in PRESETS:
            present = self.path(model_id).is_file()
            ready = available and present and model_id in self.verified
            reason = error or self.errors.get(model_id) or ('Chưa có checkpoint. Chạy setup_mac.sh.' if not present else 'Đã chạy mạng thật trên Metal/MPS.' if ready else 'Cần kiểm tra mạng: bấm Lưu & kiểm tra để chạy xác minh MPS.')
            result.append({'id':model_id,'classes':GUIDELINE_LABELS,'ready':ready,'reason':reason})
        return result

    def verify(self):
        import torch
        if not torch.backends.mps.is_available():
            return self.status()
        # Full graph on a small nonempty cloud; readiness requires forward success.
        sample = np.array([[5,2,0,10],[5.1,2.1,.2,20],[10,-3,-1,5]],dtype=np.float32)
        for model_id in PRESETS:
            if model_id not in self.verified and self.path(model_id).is_file():
                try:
                    self.infer(sample,model_id,.99)
                except Exception as error:
                    self.errors[model_id] = str(error)
        return self.status()

    def infer(self, points, model_id, threshold, intensity_scale=1.0, device='mps'):
        import torch
        if not math.isfinite(threshold) or not 0<=threshold<=1:
            raise ValueError('Threshold phải từ 0 đến 1.')
        prepared = mac_model_points(points,model_id,intensity_scale)
        decorated,coords,_ = pillars(prepared,model_id)
        with self.lock, torch.inference_mode():
            network = self.load(model_id,device)
            heads = network.forward(decorated,coords)
            result = network.decode(heads,threshold)
            if device=='mps':
                self.verified[model_id]=True
                self.errors.pop(model_id,None)
            return result
