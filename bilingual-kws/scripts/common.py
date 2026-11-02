"""Shared corpus contracts. Audio and speaker identifiers stay outside Git."""
from pathlib import Path
import hashlib, json, os, unicodedata

PROJECT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get('KWS_DATA', '/home/fred/bilingual-kws-data'))
LABELS = ['UP','DOWN','LEFT','RIGHT','ANGRY','HAPPY','TIRED','NORMAL','UNKNOWN','SILENCE']
WORDS = {
 'en': {'UP':['up'], 'DOWN':['down'], 'LEFT':['left'], 'RIGHT':['right'],
        'ANGRY':['angry'], 'HAPPY':['happy'], 'TIRED':['tired'], 'NORMAL':['normal']},
 'fr': {'UP':['haut','en haut'], 'DOWN':['bas','en bas'], 'LEFT':['gauche','à gauche'],
        'RIGHT':['droite','à droite'], 'ANGRY':['fâché','en colère'],
        'HAPPY':['content','heureux'], 'TIRED':['fatigué','fatiguée'],
        'NORMAL':['normal','normale']}}
MSWC_PIN='0bc9df68e92fd6bb54176bf7eb29e2b9e97cb218'
MSWC=f'https://huggingface.co/datasets/MLCommons/ml_spoken_words/resolve/{MSWC_PIN}/data'
HOMOPHONE_NEGATIVES={'en':{'write','wright'},'fr':{'eau','au','aux','ô','oh','bat','bats','bât','bah','fâchée'}}

def normalize(s): return unicodedata.normalize('NFC',s).strip().lower()
def label(word,lang):
 for action,variants in WORDS[lang].items():
  if normalize(word) in variants:return action
 return 'UNKNOWN'
def split(group):
 v=int(hashlib.sha256(('kws-v1:'+group).encode()).hexdigest()[:8],16)%100
 return 'test' if v<12 else 'validation' if v<24 else 'train'
def digest(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def save(path,obj):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def rows():
 for p in sorted((DATA/'manifests').glob('*.jsonl')):
  for line in p.open():yield json.loads(line)
