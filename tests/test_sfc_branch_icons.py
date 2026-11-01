import json
from pathlib import Path
import re,sys,unittest,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from sfc_branch_icons import icons,gp_source,resources,resource_name

class NativeBars(unittest.TestCase):
 def test_single_and_double_horizontal_bars_are_distinct_and_bounded(self):
  definitions=json.loads((ROOT/'web/sfc-bars.json').read_text())
  for token,svg in icons(ROOT).items():
   tree=ET.fromstring(svg);self.assertEqual(tree.attrib['viewBox'],'0 0 36 18')
   paths=tree.findall('{http://www.w3.org/2000/svg}path');lines=[line for p in paths for line in re.findall(r'M(\d+),(\d+)L(\d+),(\d+)',p.attrib['d'])]
   horizontal=sum(y1==y2 for x1,y1,x2,y2 in lines)
   self.assertEqual(horizontal,definitions[token]['bars'])
   self.assertTrue(all(0<=int(x)<=36 and 0<=int(y)<=18 for x1,y1,x2,y2 in lines for x,y in [(x1,y1),(x2,y2)]))
 def test_split_and_join_stems_have_opposite_directions(self):
  definitions=json.loads((ROOT/'web/sfc-bars.json').read_text())
  for kind in ['OR','AND']:
   split=definitions[f'#SFC_{kind}_SPLIT#']['lines'];join=definitions[f'#SFC_{kind}_JOIN#']['lines']
   self.assertEqual(sum(x1==x2 and y1==0 for x1,y1,x2,y2 in split),1)
   self.assertEqual(sum(x1==x2 and y1==0 for x1,y1,x2,y2 in join),2)
 def test_svg_tokens_do_not_break_the_native_word_based_spec_parser(self):
  self.assertTrue(all(not any(c.isspace() for c in t) for t in icons(ROOT)))
  self.assertIn(b'to sfcBarSVG token',gp_source(ROOT))
 def test_native_labels_use_resource_names_instead_of_inline_svg(self):
  source=gp_source(ROOT).decode()
  self.assertNotIn('#SVG#<svg',source)
  for token in icons(ROOT):
   name=resource_name(token)
   self.assertIn("return '#SVG#"+name+"'",source)
   self.assertIn('/img/'+name+'.svg',resources(ROOT))
 def test_each_disconnected_line_has_own_path_for_the_GP_svg_parser(self):
  for svg in icons(ROOT).values():
   paths=ET.fromstring(svg).findall('{http://www.w3.org/2000/svg}path')
   self.assertGreaterEqual(len(paths),4)
   for p in paths:self.assertRegex(p.attrib['d'],r'^M\d+,\d+L\d+,\d+$')
if __name__=='__main__':unittest.main()
