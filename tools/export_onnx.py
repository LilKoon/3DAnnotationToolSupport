import os
from pathlib import Path

def main():
    try:
        from ultralytics import YOLO
    except ImportError:
        print("Please install ultralytics first: pip install ultralytics")
        return

    model_path = Path(__file__).resolve().parents[1] / 'models/yolo11n.pt'
    if not model_path.exists():
        print(f"Model not found at {model_path}. Please download the checkpoint first.")
        return

    print(f"Loading {model_path} for ONNX export...")
    model = YOLO(str(model_path))
    
    # Export to ONNX
    print("Exporting to ONNX format...")
    success = model.export(format='onnx')
    
    if success:
        onnx_path = model_path.with_suffix('.onnx')
        print(f"Export successful! ONNX model saved at: {onnx_path}")
    else:
        print("Export failed.")

if __name__ == '__main__':
    main()
