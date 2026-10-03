"""Local image detection. Never download models implicitly."""
import os,threading,hashlib
from pathlib import Path
from PIL import Image

class ImageDetector:
    def __init__(self):self.model=None;self.lock=threading.Lock()
    def _get_model_path(self):
        base_path = Path(os.environ.get('V4_IMAGE_CHECKPOINT',str(Path(__file__).resolve().parents[1]/'models/yolo11n.pt')))
        onnx_path = base_path.with_suffix('.onnx')
        if onnx_path.exists(): return onnx_path
        return base_path
    
    def path(self): return self._get_model_path()
    
    def status(self):
        import importlib.util
        available=bool(importlib.util.find_spec('ultralytics'));present=self.path().is_file()
        is_onnx = self.path().suffix == '.onnx'
        backend = 'ONNX Runtime' if is_onnx else 'local CPU'
        return {'ready':available and present,'model':'YOLO11n' + (' (ONNX)' if is_onnx else ''),'backend':backend,'reason':f'Sẵn sàng chạy ảnh cục bộ ({backend})' if available and present else 'Chạy ../venv/bin/python tools/setup_image.py để tải checkpoint YOLO11n; cần ultralytics','license':'Ultralytics AGPL-3.0 / Enterprise','classes':list(self.model.names.values()) if self.model else []}
    
    def infer(self,image_path,threshold=.25):
        if not self.status()['ready']:raise RuntimeError(self.status()['reason'])
        if not 0<=threshold<=1:raise ValueError('Invalid image confidence')
        with self.lock:
            from ultralytics import YOLO
            if self.model is None:self.model=YOLO(str(self.path()))
            # For ONNX, ultralytics might not support 'device=cpu' kwarg if onnxruntime is doing it, but it usually ignores it gracefully
            with Image.open(image_path) as image:results=self.model.predict(image.convert('RGB'),conf=threshold,imgsz=640,save=False,verbose=False,max_det=100)
            result=results[0];detections=[]
            if result.boxes is not None:
                for i,(bbox,confidence,label) in enumerate(zip(result.boxes.xyxy.cpu().tolist(),result.boxes.conf.cpu().tolist(),result.boxes.cls.cpu().tolist())):
                    detections.append({'id':str(i),'label':result.names[int(label)],'bbox':bbox,'confidence':float(confidence)})
            return {'model':'YOLO11n','checkpoint_sha256':hashlib.sha256(self.path().read_bytes()).hexdigest(),'detections':detections}

image_detector=ImageDetector()
