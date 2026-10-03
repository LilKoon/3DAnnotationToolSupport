import unittest
from pathlib import Path
from tempfile import mkdtemp

import numpy as np
from io import BytesIO
from PIL import Image
from fastapi.testclient import TestClient
from unittest.mock import patch
from types import SimpleNamespace

from core.geometry import Cuboid, cvat_points
from core.models import configured_models, detect_geometry, predictions_to_cuboids
from core.pointcloud import parse_pointcloud
from core.store import SessionStore


class PointCloudTests(unittest.TestCase):
    def test_ascii_pcd_and_bin(self):
        payload = b"VERSION .7\nFIELDS x y z intensity\nSIZE 4 4 4 4\nTYPE F F F F\nCOUNT 1 1 1 1\nWIDTH 2\nHEIGHT 1\nPOINTS 2\nDATA ascii\n1 2 3 0.5\n4 5 6 0.8\n"
        points = parse_pointcloud(payload, "frame.pcd")
        np.testing.assert_allclose(points[0], [1, 2, 3, .5])
        np.testing.assert_allclose(parse_pointcloud(points.astype("<f4").tobytes(), "frame.bin"), points)

    def test_rejects_invalid_data(self):
        with self.assertRaises(ValueError):
            parse_pointcloud(b"bad", "frame.bin")
        with self.assertRaises(ValueError):
            parse_pointcloud(b"POINTS 2\nDATA binary_compressed\n", "frame.pcd")


class CuboidTests(unittest.TestCase):
    def test_cvat_3d_points_and_sign_validation(self):
        box = Cuboid(id="a", label="Car", center=[1, 2, 3], size=[4, 2, 2], yaw=.5)
        self.assertEqual(len(cvat_points(box)), 16)
        self.assertEqual(cvat_points(box)[:9], [1, 2, 3, 0, 0, .5, 4, 2, 2])
        with self.assertRaises(ValueError):
            Cuboid(id="a", label="Car", center=[1, 2, 3], size=[-1, 2, 3])

    def test_session_revision_and_durable_edit(self):
        root = Path(mkdtemp(prefix="v3-test-"))
        store = SessionStore(root)
        session = store.create(np.array([[1, 2, 3, 4]], dtype=np.float32), "test")
        box = Cuboid(id="a", label="Car", center=[1, 2, 3], size=[4, 2, 2], axis_signs=[-1, 1, -1])
        saved = store.update(session["id"], 0, [box])
        self.assertEqual(store.load(session["id"])["boxes"][0]["axis_signs"], [-1, 1, -1])
        self.assertEqual(saved["revision"], 1)
        with self.assertRaisesRegex(ValueError, "Stale"):
            store.update(session["id"], 0, [])
        self.assertTrue((root / session["id"] / "00000000.json").exists())

    def test_cpu_geometry_proposals(self):
        rng = np.random.default_rng(7)
        road = np.column_stack([rng.uniform(1, 11, 1400), rng.uniform(-4, 4, 1400), rng.normal(-1.5, .025, 1400), np.ones(1400)])
        car = np.column_stack([rng.uniform(4, 7, 500), rng.uniform(-1, 1, 500), rng.uniform(-1.1, .2, 500), np.ones(500)])
        proposals = detect_geometry(np.vstack([road, car]).astype(np.float32))
        self.assertTrue(any(box.label == "Car" and 4 <= box.center[0] <= 7 for box in proposals))

    def test_cpu_model_ready(self):
        self.assertTrue(next(model for model in configured_models() if model["id"] == "geometry-cpu")["ready"])

    def test_model_bottom_center_becomes_geometry_center(self):
        boxes = predictions_to_cuboids(np.array([[3, 2, -1.5, 4, 2, 1.6, .2]]), np.array([.9]), np.array([0]), ["Car"], "test", .3)
        self.assertAlmostEqual(boxes[0].center[2], -.7)
        self.assertEqual(boxes[0].size, [4, 2, 1.6])


class ApiTests(unittest.TestCase):
    def test_upload_edit_camera_reload(self):
        from api import server
        previous = server.store
        server.store = SessionStore(Path(mkdtemp(prefix="v3-api-test-")))
        try:
            client = TestClient(server.app)
            cloud = np.array([[1, 2, 3, 1], [4, 5, 6, 1]], dtype="<f4")
            response = client.post("/api/sessions/upload?filename=frame.bin", content=cloud.tobytes())
            self.assertEqual(response.status_code, 200)
            session_id = response.json()["id"]
            self.assertEqual(len(client.get(f"/api/sessions/{session_id}").json()["points"]), 2)
            box = Cuboid(id="box", label="Car", center=[1, 2, 3], size=[4, 2, 1]).model_dump()
            saved = client.put(f"/api/sessions/{session_id}", json={"revision": 0, "boxes": [box]})
            self.assertEqual(saved.status_code, 200)
            stale = client.put(f"/api/sessions/{session_id}", json={"revision": 0, "boxes": [box]})
            self.assertEqual(stale.status_code, 409)
            image = BytesIO()
            Image.new("RGB", (2, 2), "red").save(image, format="PNG")
            camera = client.post(f"/api/sessions/{session_id}/cameras?filename=rear.png", content=image.getvalue())
            self.assertEqual(camera.status_code, 200)
            self.assertEqual(client.get(f"/api/sessions/{session_id}/cameras/0").status_code, 200)
            self.assertEqual(client.get(f"/api/sessions/{session_id}").json()["boxes"][0]["id"], "box")
        finally:
            server.store = previous

    def test_publish_accepted_cuboids_appends_without_replacing(self):
        from api import server
        previous = server.store
        server.store = SessionStore(Path(mkdtemp(prefix="v3-publish-test-")))
        try:
            session = server.store.create(np.array([[1, 2, 3, 1]], dtype=np.float32), "CVAT frame", ["Car"], {"url": "https://cvat.example.com", "job_id": 1, "frame": 7})
            box = Cuboid(id="accepted", frame=7, label="Car", center=[1, 2, 3], size=[4, 2, 1], status="accepted")
            server.store.update(session["id"], 0, [box])

            class FakeJob:
                def __init__(self):
                    self.calls = []

                def get_labels(self):
                    return [SimpleNamespace(name="Car", id=10, attributes=[])]

                def update_annotations(self, data, action):
                    self.calls.append((data, action))

            job = FakeJob()
            with patch.object(server.Credentials, "connect", return_value=(None, job)):
                client = TestClient(server.app)
                payload = {"url": "https://cvat.example.com", "username": "test", "password": "test", "job_id": 1, "confirm": True}
                first = client.post(f"/api/sessions/{session['id']}/publish", json=payload)
                self.assertEqual(first.status_code, 200, first.text)
                self.assertEqual(first.json()["published"], 1)
                self.assertEqual(len(job.calls), 1)
                self.assertEqual(len(job.calls[0][0].shapes[0].points), 16)
                second = client.post(f"/api/sessions/{session['id']}/publish", json=payload)
                self.assertEqual(second.json()["published"], 0)
                self.assertEqual(len(job.calls), 1)
        finally:
            server.store = previous

    def test_detection_maps_model_class_to_cvat_label(self):
        from api import server
        previous = server.store
        server.store = SessionStore(Path(mkdtemp(prefix="v3-map-test-")))
        try:
            session = server.store.create(np.array([[1, 2, 3, 1]], dtype=np.float32), "frame", ["Vehicle"])
            proposal = Cuboid(id="model-car", label="Car", center=[1, 2, 3], size=[4, 2, 1], source="geometry-cpu")
            with patch.object(server, "detect", return_value=[proposal]):
                response = TestClient(server.app).post(f"/api/sessions/{session['id']}/detect", json={"revision": 0, "model_id": "geometry-cpu", "label_map": {"Car": "Vehicle"}})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["boxes"][0]["label"], "Vehicle")
        finally:
            server.store = previous


if __name__ == "__main__":
    unittest.main()
