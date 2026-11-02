"""Render the reviewed capability index without guessing runtime availability."""
# SPDX-License-Identifier: MIT
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
IMPLEMENTATION={'implemented','partial','planned','unavailable','unassessed'}
VALIDATION={'physical_target','physical_limited','software_only','host_ci','simulation','source_only','not_tested'}
FAMILIES={'bare_metal','zephyr','linux'}
CPU={'propeller2_32','xtensa_32','riscv_32','arm_32','arm_64','x86_64'}

def validate(value,root=ROOT):
    if value.get('schema')!=1:raise ValueError('Capability index schema1 required')
    features=[f['id'] for f in value['features']]
    if not features or len(set(features))!=len(features):raise ValueError('Unique feature IDs required')
    ids=set()
    def reference(name):
        if name.startswith('https://'):return
        path=Path(name)
        if path.is_absolute() or '..' in path.parts or not (root/path).is_file():raise ValueError('Missing/unsafe evidence source: '+name)
    for target in value['targets']:
        if target['id'] in ids:raise ValueError('Duplicate target')
        ids.add(target['id'])
        if target['runtime_family'] not in FAMILIES or target['cpu_architecture'] not in CPU:raise ValueError('Execution family and CPU must be explicit distinct fields')
        if not target.get('sources'):raise ValueError('Target sources required')
        for name in target['sources']:reference(name)
        for name,digest in target.get('reviewed_source_hashes',{}).items():
            reference(name)
            if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:raise ValueError('Hardware manifest changed; re-audit its matrix summary: '+name)
        if set(target['features'])-set(features):raise ValueError('Unknown feature ID')
        for feature,cell in target['features'].items():
            if cell['implementation'] not in IMPLEMENTATION or cell['validation'] not in VALIDATION:raise ValueError('Invalid capability status')
            if cell['implementation'] in {'implemented','partial'} and not cell.get('backend'):raise ValueError('Implemented feature requires an explicit backend')
            if not cell.get('limits') or not cell.get('evidence'):raise ValueError('Claims require scope/limits and evidence')
            if cell['validation'] in {'physical_target','physical_limited'} and (target['project_status']!='physical_target' or cell['implementation'] not in {'implemented','partial'}):raise ValueError('Physical feature claim requires target acceptance and an implementation')
            if target['project_status']=='planned_target' and cell['implementation'] in {'implemented','partial'}:raise ValueError('A planned target cannot inherit an implementation from its CPU/family')
            for name in cell['evidence']:reference(name)
        if 'camera' in target:
            for name in target['camera']['evidence']:reference(name)
    return value

def load(path=ROOT/'capabilities/matrix.json',root=ROOT):
    return validate(json.loads(Path(path).read_text(encoding='utf-8')),root)

def short(cell):
    impl=cell['implementation'];test=cell['validation']
    if impl=='unassessed':return 'Non évalué'
    if impl=='planned':return 'Prévu'
    if impl=='unavailable':return 'Indisponible'
    if impl=='partial':return 'Partiel / simulé' if test=='simulation' else 'Partiel'
    return {'physical_target':'Testé matériel','physical_limited':'Testé / limites','software_only':'Logiciel testé','host_ci':'Testé hôte CI','simulation':'Impl. / simulé','source_only':'Impl. / non testé','not_tested':'Impl. / non testé'}[test]

def link(name):return '['+name+']('+('' if name.startswith('https://') else '../')+name+')'
def clean(text):return str(text).replace('|','/').replace('\n',' ')

def render(value):
    lines=['# Matrice cartes × fonctionnalités','',
     'Index audité au '+value['review_date']+'. Famille d’exécution, architecture CPU et capacités sont trois axes distincts.',
     'Les manifestes matériels par cible restent canoniques. Ce tableau résume leurs preuves et les limites du dépôt ; il ne configure aucun matériel.',
     'Un bloc commun peut utiliser différents backends. Une dépendance installée, un même CPU ou une API amont ne valent pas prise en charge validée.','',
     '« Testé matériel » désigne la cible et le périmètre cités ; « Testé / limites » conserve un résultat partiel ou une restriction.',
     '« Logiciel testé » ne valide aucun capteur. Les tests hôte CI et les simulations sont distincts des essais sur la carte.',
     '« Indisponible » signifie absent/non fourni dans ce port, sans conclure à une impossibilité matérielle. « Non évalué » n’est jamais « disponible ».','',
     '| Cible | Famille | CPU | NN | Voix / Whistle | Capteurs | OLED I²C | MQTT | SQLite | Capture caméra | Traitement image |',
     '|---|---|---|---|---|---|---|---|---|---|---|']
    for target in value['targets']:
        cells=[short(target['features'].get(feature['id'],value['unknown_default'])) for feature in value['features']]
        lines.append('| '+' | '.join(map(clean,[target['label'],target['runtime_family'],target['cpu_architecture'],*cells]))+' |')
    lines+=['','## Prérequis et contrat commun','',
     'Les identifiants ci-dessous sont des catégories de catalogue, pas la promesse de primitives/blocs déjà implémentés sur toutes les cartes.','']
    for feature in value['features']:lines.append('- **'+feature['label']+'** (`'+feature['id']+'`) : '+feature['prerequisites'])
    lines+=['','## Périmètre par matériel','']
    for target in value['targets']:
        lines+=['### '+target['label'],'',
         '- Famille : `'+target['runtime_family']+'` ; CPU : `'+target['cpu_architecture']+'` ; état du port : `'+target['project_status']+'`.',
         '- VM : '+target['vm']+' ; Arduino core : `'+target['arduino_core']+'`.',
         '- Tests : '+target['hardware_tests'],
         '- Sources : '+', '.join(link(name) for name in target['sources'])+'.','']
        for feature in value['features']:
            cell=target['features'].get(feature['id'])
            if not cell:continue
            lines.append('- **'+feature['label']+' — '+short(cell)+'** : '+(cell['backend']+' ; ' if cell['backend'] else '')+cell['limits']+' État déclaré : `'+cell['availability']+'`. Preuves : '+', '.join(link(name) for name in cell['evidence'])+'.')
        if 'camera' in target:
            camera=target['camera']
            lines+=['','Caméra :','',
             '- Capture native : '+str(camera['capture'])+' ; réception seulement : '+str(camera['receive_only'])+'.',
             '- Pilote : '+str(camera['driver'] or 'non validé/non fourni')+'.',
             '- Formats capteur : '+(', '.join(camera['sensor_formats']) if camera['sensor_formats'] else 'non validés')+'.',
             '- Formats de sortie : '+(', '.join(camera['output_formats']) if camera['output_formats'] else 'non validés')+'.',
             '- Résolutions de capture : '+(json.dumps(camera['capture_resolutions'],ensure_ascii=False) if camera['capture_resolutions'] else 'non validées')+'.',
             '- Résolutions de prévisualisation : '+(json.dumps(camera['preview_resolutions'],ensure_ascii=False) if camera['preview_resolutions'] else 'non validées')+'.',
             '- Codecs : '+(json.dumps(camera['codecs'],ensure_ascii=False) if camera['codecs'] else 'non validés')+' ; qualité : `'+camera['quality_gate']+'`.']
        lines.append('')
    lines+=['## Utilisation future par l’éditeur','',
     'La source lisible par machine est [capabilities/matrix.json](../capabilities/matrix.json). Les sources matérielles revues sont liées par empreinte ; si elles changent, réauditer la synthèse plutôt que conserver une copie divergente.',
     'L’éditeur doit combiner le contrat commun, le manifeste de la cible, les capacités réellement rapportées, la configuration et la disponibilité des ressources. Ce catalogue documentaire seul ne doit ni activer un bloc ni autoriser un accès matériel.',
     'Une cible sans rapport fiable reste inconnue. Préserver les définitions des blocs des projets existants et expliquer les fonctions non disponibles. Le filtrage de la palette Python reste à implémenter dans une interface commune ; le runtime refuse déjà les extensions désactivées.',
     'MicroDuck : ne jamais forcer le profil Blinka Radxa. UART2 est réservé aux moteurs selon le test opérateur rapporté ; utiliser les interfaces robot appropriées, sans transfert de validation depuis le Pi5.','',
     'Régénération : `python tools/capability_matrix.py` ; vérification sans écriture : `python tools/capability_matrix.py --check`.','']
    return '\n'.join(lines)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    value=load();text=render(value);destination=ROOT/'docs/CAPABILITY_MATRIX.md'
    if args.check:
        if destination.read_text(encoding='utf-8')!=text:raise SystemExit('Capability matrix is stale; regenerate it from reviewed sources')
    else:destination.write_text(text,encoding='utf-8',newline='\n')
    print(json.dumps({'targets':len(value['targets']),'features':len(value['features']),'checked':args.check,'runtime_capability_filter_implemented':False}))
if __name__=='__main__':main()
