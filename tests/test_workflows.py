import base64
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

from archdiagram.emit.drawio import emit_drawio
from archdiagram.emit.pptx import emit_pptx
from archdiagram.emit.svg import render_html, render_svg
from archdiagram.emit.svgcanvas import edge_endpoints
from archdiagram.emit.vsdx import emit_vsdx
from archdiagram.layout.engine import layout_diagram
from archdiagram.registry.catalog import get_catalog
from archdiagram.spec.model import Edge
from archdiagram.spec.validate import SpecValidationError, validate_spec
from archdiagram.templates import get_template, list_templates, suggest_template


class TestWorkflows(unittest.TestCase):
    def test_templates_validate_and_choose(self):
        for item in list_templates():
            self.assertGreater(len(validate_spec(get_template(item['name'])).nodes), 0)
        self.assertEqual(suggest_template('handoff between two teams'), 'swimlane')
        self.assertEqual(suggest_template('approval process'), 'decision')
        self.assertEqual(suggest_template('ETL pipeline'), 'dataflow')
        self.assertEqual(suggest_template('AWS services'), 'cloud')

    def test_rejects_missing_or_unknown_lanes_and_kinds(self):
        spec = get_template('swimlane')
        del spec['nodes'][0]['lane']
        spec['nodes'][1]['kind'] = 'unknown'
        with self.assertRaises(SpecValidationError) as ctx:
            validate_spec(spec)
        self.assertTrue(any('lane' in e for e in ctx.exception.errors))
        self.assertTrue(any('kind' in e for e in ctx.exception.errors))

    def test_lanes_contain_nodes_without_overlap(self):
        for direction in ('LR', 'TB', 'RL', 'BT'):
            spec = get_template('swimlane')
            spec['direction'] = direction
            d = validate_spec(spec)
            layout = layout_diagram(d)
            for node in d.nodes:
                box = layout.boxes[node.id]
                lane = layout.lane_boxes[node.lane]
                self.assertGreaterEqual(box.x, lane.x)
                self.assertGreaterEqual(box.y, lane.y)
                self.assertLessEqual(box.x + box.w, lane.x + lane.w)
                self.assertLessEqual(box.y + box.h, lane.y + lane.h)
            for i, first in enumerate(d.nodes):
                for second in d.nodes[i+1:]:
                    a, b = layout.boxes[first.id], layout.boxes[second.id]
                    self.assertTrue(a.x+a.w <= b.x or b.x+b.w <= a.x or
                                    a.y+a.h <= b.y or b.y+b.h <= a.y)

    def test_cycle_uses_one_layer_then_progresses(self):
        spec = get_template('workflow')
        spec['edges'].append({'source': 'check', 'target': 'work', 'label': 'Retry'})
        d = validate_spec(spec)
        boxes = layout_diagram(d).boxes
        self.assertEqual(boxes['work'].x, boxes['check'].x)
        self.assertLess(boxes['start'].x, boxes['work'].x)
        self.assertLess(boxes['work'].x, boxes['record'].x)

    def test_reciprocal_edges_have_distinct_routes(self):
        d = validate_spec(get_template('workflow'))
        d.edges.append(Edge('check', 'work'))
        layout = layout_diagram(d)
        forward = next(e for e in d.edges if e.source == 'work' and e.target == 'check')
        backward = d.edges[-1]
        a = edge_endpoints(d, layout, forward)
        b = edge_endpoints(d, layout, backward)
        self.assertNotEqual((a[0], a[1]), (b[2], b[3]))

    def test_exports_have_editable_workflow_shapes(self):
        d = validate_spec(get_template('swimlane'))
        svg, _ = render_svg(d)
        html, _ = render_html(d)
        ET.fromstring(svg)
        self.assertIn('<polygon', svg)
        self.assertIn('Reviewer', svg)
        self.assertIn('<svg', html)
        drawio = ET.fromstring(emit_drawio(d))
        cells = {c.get('id'): c for c in drawio.iter('mxCell')}
        self.assertIn('lane_reviewer', cells)
        self.assertIn('rhombus', cells['node_review'].get('style'))
        with tempfile.TemporaryDirectory() as tmp:
            vsdx = os.path.join(tmp, 'workflow.vsdx')
            pptx = os.path.join(tmp, 'workflow.pptx')
            emit_vsdx(d, vsdx)
            emit_pptx(d, pptx)
            for path in (vsdx, pptx):
                with zipfile.ZipFile(path) as zf:
                    self.assertIsNone(zf.testzip())
                    for name in zf.namelist():
                        if name.endswith('.xml') or name.endswith('.rels'):
                            ET.fromstring(zf.read(name))
            with zipfile.ZipFile(pptx) as zf:
                slide = zf.read('ppt/slides/slide1.xml').decode()
                self.assertIn('prst="diamond"', slide)
                self.assertIn('Submit', slide)
                self.assertIn('Approve?', slide)

    def test_powerpoint_embeds_service_icon_when_available(self):
        d = validate_spec({'nodes': [{'id': 'app', 'service': 'gcp.cloud_run'}]})
        icon = get_catalog().lookup('gcp.cloud_run').icon
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, *icon.split('/'))
            os.makedirs(os.path.dirname(path))
            with open(path, 'wb') as fh:
                fh.write(base64.b64decode(
                    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9xUAAAAABJRU5ErkJggg=='
                ))
            out = os.path.join(tmp, 'icon.pptx')
            self.assertEqual(emit_pptx(d, out, icon_cache=tmp), [])
            with zipfile.ZipFile(out) as zf:
                self.assertIn('ppt/media/image1.png', zf.namelist())
                self.assertIn(b'r:embed="rId2"', zf.read('ppt/slides/slide1.xml'))


if __name__ == '__main__':
    unittest.main()
