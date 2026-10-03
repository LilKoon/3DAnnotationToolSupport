import unittest
import numpy as np
from core.pointcloud import parse_pointcloud

class PointColorsTests(unittest.TestCase):
    def test_ascii_packed_rgb_preserves_geometry(self):
        data=b'FIELDS x y z rgb\nSIZE 4 4 4 4\nTYPE F F F U\nCOUNT 1 1 1 1\nPOINTS 2\nDATA ascii\n1 2 3 16711680\n4 5 6 65280\n'
        points,colors=parse_pointcloud(data,'frame.pcd',with_colors=True)
        np.testing.assert_array_equal(colors,[[255,0,0],[0,255,0]])
        np.testing.assert_array_equal(points,[[1,2,3,0],[4,5,6,0]])
    def test_binary_float_packed_rgb(self):
        record=np.array([(1,2,3,0x123456)],dtype=[('x','<f4'),('y','<f4'),('z','<f4'),('rgb','<u4')])
        data=b'FIELDS x y z rgb\nSIZE 4 4 4 4\nTYPE F F F F\nCOUNT 1 1 1 1\nPOINTS 1\nDATA binary\n'+record.tobytes()
        _,colors=parse_pointcloud(data,'frame.pcd',with_colors=True)
        np.testing.assert_array_equal(colors,[[0x12,0x34,0x56]])
    def test_colorless_bin_returns_no_colors(self):
        data=np.array([[1,2,3,.5]],dtype='<f4').tobytes()
        points,colors=parse_pointcloud(data,'frame.bin',with_colors=True)
        self.assertIsNone(colors)
        self.assertEqual(points.shape,(1,4))
    def test_api_colors_survive_reload_and_do_not_enter_model_input(self):
        from pathlib import Path
        from tempfile import mkdtemp
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from api import server
        from core.store import SessionStore
        data=b'FIELDS x y z r g b\nSIZE 4 4 4 1 1 1\nTYPE F F F U U U\nCOUNT 1 1 1 1 1 1\nPOINTS 2\nDATA ascii\n1 2 3 255 0 0\n4 5 6 0 255 0\n'
        store=SessionStore(Path(mkdtemp(prefix='v3-rgb-test-')))
        with patch.object(server,'store',store):
            client=TestClient(server.app)
            response=client.post('/api/sessions/upload?filename=rgb.pcd',content=data)
            self.assertEqual(response.status_code,200,response.text)
            session=response.json()
            loaded=client.get('/api/sessions/'+session['id']).json()
            self.assertEqual(loaded['point_colors'],[[255,0,0],[0,255,0]])
            self.assertEqual(len(loaded['points'][0]),4)
            self.assertEqual(np.fromfile(store.bin_path(session['id']),dtype='<f4').reshape(-1,4).shape,(2,4))
    def test_ascii_float_rgba_and_display_sampling(self):
        from core.pointcloud import display_points
        packed=np.array([0xff123456],dtype='<u4').view('<f4')[0]
        data=('FIELDS x y z rgba\nSIZE 4 4 4 4\nTYPE F F F F\nCOUNT 1 1 1 1\nPOINTS 1\nDATA ascii\n1 2 3 '+str(packed)+'\n').encode()
        _,colors=parse_pointcloud(data,'rgba.pcd',with_colors=True)
        np.testing.assert_array_equal(colors,[[18,52,86]])
        points=np.zeros((100001,4));points[:,0]=np.arange(len(points))
        colors=np.column_stack([np.arange(len(points))%256]*3).astype('u1')
        self.assertEqual(len(display_points(points)),len(display_points(colors)))
        self.assertEqual(display_points(colors)[1],[2,2,2])
