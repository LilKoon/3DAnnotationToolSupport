import unittest,math
from core.geometry import Cuboid
from core.evaluation_v4 import compare_annotations,quality_report

class EvaluationV4Tests(unittest.TestCase):
    def box(self,id,**kw):return Cuboid(id=id,label='car',center=[5,0,1],size=[4,2,2],**kw)
    def test_rotation_and_iou_without_renaming_map(self):
        a=self.box('a',yaw=math.pi/2);b=self.box('b')
        result=compare_annotations([a],[b]);self.assertEqual(result['tp'],1);self.assertAlmostEqual(result['rotation_error_deg'],90);self.assertAlmostEqual(result['mean_iou3d'],1/3);self.assertIn('center matching',result['protocol'])
    def test_tilted_iou_is_explicitly_unsupported(self):
        result=compare_annotations([self.box('a',pitch=.3)],[self.box('b')]);self.assertIsNone(result['mean_iou3d']);self.assertEqual(result['iou_supported_pairs'],0)
    def test_quality_report_does_not_change_boxes(self):
        boxes=[self.box('a'),self.box('b')];before=[b.model_dump() for b in boxes];report=quality_report(boxes)
        self.assertEqual(report['overlapping_pairs'],[['a','b']]);self.assertEqual(before,[b.model_dump() for b in boxes])
