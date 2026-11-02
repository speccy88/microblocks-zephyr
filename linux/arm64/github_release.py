"""Read-only discovery of compatible releases from this port's GitHub project.

No upstream board firmware, client URLs, credentials, TLS exceptions or install.
The existing updater performs explicit selection, apply, backup and recovery.
"""
# SPDX-License-Identifier: MPL-2.0
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPRedirectHandler, ProxyHandler, Request
import uuid

from browser_update import MAX_UPLOAD, SHA, VERSION, UpdateError, review_archive, unique

REPOSITORY='speccy88/microblocks-zephyr'
API='https://api.github.com/repos/'+REPOSITORY
DOWNLOAD='https://github.com/'+REPOSITORY+'/releases/download/'
COMMIT=re.compile(r'[a-f0-9]{40}')
KNOWN_BASELINES={'d60102ce79a73f79ee63d094e79c0803e64fdfb8cb4949a688639e9e89d09a2b':'548fea9392ffabd23a3aa550a813099e9940d9c3'}


def safe_url(url):
    parsed=urlsplit(url)
    if (parsed.scheme!='https' or parsed.hostname not in {'api.github.com','github.com','release-assets.githubusercontent.com','objects.githubusercontent.com'}
            or parsed.username or parsed.password or parsed.port not in (None,443) or parsed.fragment):
        raise UpdateError('Redirection GitHub non autorisée; aucun paquet installé')
    return url


class Redirect(HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,message,headers,newurl):
        safe_url(newurl)
        return super().redirect_request(request,fp,code,message,headers,newurl)


class GitHubReleases:
    def __init__(self,updater,opener=None):
        self.updater=updater
        self.opener=opener or build_opener(ProxyHandler({}),Redirect())
        self.choices={};self.last=None;self.last_time=0;self.deadline=0

    def config(self):return json.loads((self.updater.root/'service.json').read_text())

    def fetch(self,url,limit,*,destination=None,progress=lambda value:None):
        safe_url(url)
        remaining=self.deadline-time.monotonic()
        if remaining<=0:raise UpdateError('Délai de recherche GitHub dépassé; réessayez sans changer le SmallVM')
        headers={'User-Agent':'MicroBlocks-Pi-Updater/1','Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2026-03-10'}
        try:
            with self.opener.open(Request(url,headers=headers),timeout=min(10,remaining)) as response:
                safe_url(response.geturl())
                length=response.headers.get('Content-Length')
                if length is not None and (not length.isdigit() or int(length)>limit):raise UpdateError('Réponse GitHub trop grande')
                result=bytearray();received=0
                out=destination.open('xb') if destination else None
                try:
                    while True:
                        if time.monotonic()>self.deadline:raise UpdateError('Téléchargement GitHub trop long; aucun paquet installé')
                        chunk=response.read(65536)
                        if not chunk:break
                        received+=len(chunk)
                        if received>limit:raise UpdateError('Réponse GitHub trop grande')
                        if out:out.write(chunk);progress({'state':'github_downloading','received':received,'total':int(length) if length else 0})
                        else:result.extend(chunk)
                finally:
                    if out:out.close()
                if length is not None and received!=int(length):raise UpdateError('Téléchargement GitHub incomplet')
                return bytes(result)
        except HTTPError as error:
            if error.code in (403,429):raise UpdateError('GitHub limite les requêtes publiques. Réessayez plus tard; aucun jeton requis.') from error
            raise UpdateError('GitHub est indisponible (HTTP '+str(error.code)+'); aucun paquet installé') from error
        except (URLError,TimeoutError,OSError) as error:
            raise UpdateError('Connexion HTTPS à GitHub impossible; vérifiez Internet sur le Pi. Aucun paquet installé.') from error

    def json(self,url):return json.loads(self.fetch(url,3*1024*1024),object_pairs_hook=unique)

    def order(self,metadata,config):
        if metadata['binary_sha256']==config['binary_sha256']:return 'current'
        baseline=config.get('native_port_commit') or KNOWN_BASELINES.get(config['binary_sha256'])
        candidate=metadata.get('port_commit')
        if not isinstance(baseline,str) or not COMMIT.fullmatch(baseline):raise UpdateError('Révision du SmallVM installé inconnue; impossible de garantir une mise à jour sans retour en arrière')
        if not isinstance(candidate,str) or not COMMIT.fullmatch(candidate):raise UpdateError('Paquet sans provenance du port; ordre des versions non vérifiable')
        if candidate==baseline:raise UpdateError('Même révision avec un autre exécutable; aucune mise à jour automatique proposée')
        compare=self.json(API+'/compare/'+baseline+'...'+candidate+'?per_page=1')
        if (not isinstance(compare,dict) or compare.get('status')!='ahead'
                or compare.get('merge_base_commit',{}).get('sha')!=baseline):
            raise UpdateError('Version plus ancienne ou divergente; aucun retour en arrière proposé')
        return 'newer'

    def check(self,include_prereleases,progress):
        config=self.config()
        cache_key=(config['binary_sha256'],include_prereleases)
        if self.last and self.last[0]==cache_key and time.monotonic()-self.last_time<30:return self.last[1]
        self.deadline=time.monotonic()+110;self.choices={}
        progress({'state':'github_checking','repository':REPOSITORY})
        releases=[]
        for page in range(1,4):
            batch=self.json(API+'/releases?per_page=30&page='+str(page))
            if not isinstance(batch,list):raise UpdateError('Catalogue GitHub invalide')
            releases.extend(batch)
            if len(batch)<30:break
        else:raise UpdateError('Catalogue GitHub trop grand pour vérifier la dernière version; aucune sélection automatique')
        candidates=[];skipped=[]
        for release in releases:
            if not isinstance(release,dict) or release.get('draft') or release.get('prerelease') and not include_prereleases:continue
            tag=release.get('tag_name');published=release.get('published_at')
            if not isinstance(tag,str) or not VERSION.fullmatch(tag) or tag=='latest' or not isinstance(published,str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ',published):continue
            name='smallvm-linux-arm64-'+tag+'.tar.gz'
            assets=release.get('assets',[])
            matches=[a for a in assets if isinstance(a,dict) and a.get('name')==name]
            if len(matches)!=1:
                skipped.append({'version':tag,'reason':'Aucun paquet natif Linux ARM64 au format de ce port'});continue
            asset=matches[0]
            if (type(release.get('id')) is not int or type(asset.get('id')) is not int or type(asset.get('size')) is not int
                    or not 64<=asset['size']<=MAX_UPLOAD or asset.get('browser_download_url')!=DOWNLOAD+tag+'/'+name):continue
            candidates.append((published,release,asset))
        candidates.sort(key=lambda entry:entry[0],reverse=True)
        found=[];up_to_date=False
        for index,(published,release,asset) in enumerate(candidates):
            if index>=5:raise UpdateError('Plus de cinq paquets récents à vérifier; aucune dernière version compatible confirmée')
            tag=release['tag_name'];temporary=self.updater.directory/('.github-'+uuid.uuid4().hex)
            try:
                progress({'state':'github_checking_asset','version':tag})
                digest=asset.get('digest')
                if not isinstance(digest,str) or not re.fullmatch(r'sha256:[a-f0-9]{64}',digest):
                    sums=[a for a in release.get('assets',[]) if a.get('name')=='SHA256SUMS']
                    if len(sums)!=1 or sums[0].get('browser_download_url')!=DOWNLOAD+tag+'/SHA256SUMS':raise UpdateError('SHA-256 GitHub ou SHA256SUMS manquant')
                    lines=self.fetch(DOWNLOAD+tag+'/SHA256SUMS',65536).decode('ascii').splitlines()
                    matches=[m[1] for line in lines if (m:=re.fullmatch(r'([a-f0-9]{64})  [*]?'+re.escape(asset['name']),line))]
                    if len(matches)!=1:raise UpdateError('Somme de contrôle unique du paquet introuvable')
                    digest=matches[0]
                else:digest=digest[7:]
                self.fetch(asset['browser_download_url'],asset['size'],destination=temporary,progress=progress)
                if temporary.stat().st_size!=asset['size']:raise UpdateError('Taille du paquet différente du catalogue GitHub')
                progress({'state':'github_validating','version':tag})
                metadata=review_archive(temporary,digest)
                if metadata['version']!=tag:raise UpdateError('Version du paquet différente de la version GitHub')
                required=config.get('required_runtime_capabilities',[])
                if not isinstance(required,list) or not set(required)<=set(metadata['capabilities']):raise UpdateError('Paquet incompatible avec les capacités Python installées')
                order=self.order(metadata,config)
                if order=='current':up_to_date=True;break
                destination=self.updater.directory/(digest+'.tar.gz')
                if destination.exists():
                    if hashlib.sha256(destination.read_bytes()).hexdigest()!=digest:raise UpdateError('Paquet local en cache modifié')
                else:temporary.replace(destination)
                token=str(release['id'])+':'+str(asset['id'])
                choice={**metadata,'choice':token,'repository':REPOSITORY,'published_at':published,
                    'prerelease':bool(release.get('prerelease')),'url':'https://github.com/'+REPOSITORY+'/releases/tag/'+tag,
                    'baseline_binary_sha256':config['binary_sha256']}
                self.choices[token]=(time.monotonic(),choice);found.append(choice);break
            except UpdateError as error:
                skipped.append({'version':tag,'reason':str(error)})
            finally:temporary.unlink(missing_ok=True)
        result={'state':'github_checked','repository':REPOSITORY,'choices':found,'up_to_date':up_to_date,
            'message':('La version publiée compatible est déjà installée.' if up_to_date else
                'Dernière version compatible vérifiée; choisissez-la avant installation.' if found else
                'Aucune version Linux ARM64 compatible plus récente publiée dans ce dépôt. Le SmallVM actuel est conservé.'),
            'skipped':skipped[:12]}
        self.last=(cache_key,result);self.last_time=time.monotonic();return result

    def choose(self,token):
        selected=self.choices.get(token)
        if not selected or time.monotonic()-selected[0]>600:raise UpdateError('Sélection GitHub expirée; relancez la recherche')
        choice=selected[1]
        if self.config()['binary_sha256']!=choice['baseline_binary_sha256']:raise UpdateError('Le SmallVM a changé; relancez la recherche GitHub')
        path=self.updater.directory/(choice['sha256']+'.tar.gz')
        metadata=self.updater.prepare(path,choice['sha256'],github=choice)
        return {'state':'prepared','native_install_enabled':self.updater.allow_apply,**metadata,'github':choice}
