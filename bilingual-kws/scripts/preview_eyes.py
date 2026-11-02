"""Generate a display-independent schematic; no device or audio APIs."""
from PIL import Image,ImageDraw,ImageFont
from common import PROJECT,LABELS
def render():
 img=Image.new('RGB',(960,470),'#101b2c');d=ImageDraw.Draw(img)
 font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',20)
 small=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14)
 for i,label in enumerate(LABELS[:8]):
  col=i%4;row=i//4;ox=col*240;oy=row*210+40
  d.rounded_rectangle((ox+10,oy,ox+230,oy+180),radius=14,fill='#162a43',outline='#38536f')
  dx=-18 if label=='LEFT' else 18 if label=='RIGHT' else 0
  dy=-15 if label=='UP' else 15 if label=='DOWN' else 0
  for ex in [ox+65+dx,ox+145+dx]:
   y=oy+65+dy;h=25 if label=='TIRED' else 48
   d.rounded_rectangle((ex-25,y,ex+25,y+h),radius=12,fill='#50e5d4')
   if label=='ANGRY':d.polygon([(ex-29,y-2),(ex+29,y-2),(ex+29,y+16)],fill='#162a43')
   if label=='HAPPY':d.ellipse((ex-30,y+14,ex+30,y+65),fill='#162a43')
  d.text((ox+120,oy+143),label,font=font,anchor='mm',fill='white')
 d.text((20,12),'Semantic eye-state preview • schematic, no physical display test',font=small,fill='#c0d2e8')
 path=PROJECT/'reports/eyes_preview.png';path.parent.mkdir(exist_ok=True);img.save(path);print(path)
if __name__=='__main__':render()
