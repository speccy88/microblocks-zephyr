"""Render reviewed board choices and installation guides without device access."""
# SPDX-License-Identifier: MPL-2.0
from html import escape
import json
from pathlib import Path
import re
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'web/js-portal/boards.json'
REPO = 'https://github.com/speccy88/microblocks-zephyr/blob/main/'
MARKER = '<!-- BOARD_CHOICES -->'


def https_url(value):
    parsed = urlparse(value)
    if parsed.scheme != 'https' or parsed.netloc not in {'github.com', 'raw.githubusercontent.com'}:
        raise ValueError('Review the installation link origin: ' + value)
    return value


def source_url(source):
    if 'path' in source:
        path = Path(source['path'])
        if path.is_absolute() or '..' in path.parts or not (ROOT / path).is_file():
            raise ValueError('Missing or unsafe installation source: ' + source['path'])
        return REPO + path.as_posix()
    return https_url(source['url'])


def load_catalog(profiles):
    value = json.loads(CATALOG.read_text(encoding='utf-8'))
    boards = value['boards']
    ids = [board['id'] for board in boards]
    if value['schema'] != 1 or len(set(ids)) != len(ids) or set(ids) != set(profiles):
        raise ValueError('Installation catalog must match every editor target exactly once')
    for board in boards:
        if not re.fullmatch(r'[a-z0-9-]+', board['id']) or not board['name'] or not board['card_note']:
            raise ValueError('Invalid installation target')
        if board['mode'] == 'browser':
            if board['id'] != 'propeller2' or board['installation_url'] != 'install/propeller2/index.html':
                raise ValueError('Only the implemented P2 browser installer is approved')
        elif board['mode'] == 'guide':
            if not board['steps'] or not board['summary'] or not board['method']:
                raise ValueError('Installation guides need a method and concrete instructions')
            if board['release']['kind'] not in {'source_only', 'older_release', 'reference_release', 'pending'}:
                raise ValueError('Review changed release availability')
            https_url(board['release']['url'])
        else:
            raise ValueError('Unknown installation method')
        for source in board['sources']:
            source_url(source)
    return value


def installation_url(board):
    return board['installation_url'] if board['mode'] == 'browser' else 'install/' + board['id'] + '/index.html'


def render_launcher(template, catalog):
    if template.count(MARKER) != 1:
        raise ValueError('Review changed launcher card anchor')
    cards = []
    for board in catalog['boards']:
        name, key = escape(board['name']), board['id']
        label = 'Install SmallVM' if board['mode'] == 'browser' else 'Install guide'
        cards.append(
            '<article class="board-card" data-board-card="' + key + '" aria-labelledby="board-' + key + '">\n'
            '<h2 id="board-' + key + '">' + name + '</h2>\n'
            '<p class="board-method">' + escape(board['card_note']) + '</p>\n'
            '<div class="board-actions">\n'
            '<a class="board-choice" data-board="' + key + '" href="js-preview/' + key + '/index.html" '
            'aria-label="Open ' + name + ' editor" target="_blank" rel="noopener">Open editor</a>\n'
            '<a class="board-install" data-install="' + key + '" href="' + installation_url(board) + '" '
            'aria-label="' + label + ' for ' + name + '" target="_blank" rel="noopener">' + label + '</a>\n'
            '</div></article>')
    return template.replace(MARKER, '\n'.join(cards))


def guide_assets(catalog, css_version):
    result = {'installation-catalog.json': (json.dumps(catalog, indent=2) + '\n').encode()}
    for board in catalog['boards']:
        if board['mode'] != 'guide':
            continue
        name = escape(board['name'])
        steps = '\n'.join('<li>' + escape(step) + '</li>' for step in board['steps'])
        links = '\n'.join('<a href="' + escape(source_url(source), quote=True) + '" target="_blank" rel="noopener noreferrer">'
                          + escape(source['label']) + '</a>' for source in board['sources'])
        release = board['release']
        html = (
            '<!doctype html>\n<!-- SPDX-License-Identifier: MPL-2.0 -->\n<html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'self\'; style-src \'self\'; script-src \'none\'; object-src \'none\'; base-uri \'self\'">'
            '<title>Install SmallVM: ' + name + '</title><link rel="stylesheet" href="../../portal.css?v=' + css_version + '"></head>\n'
            '<body><header class="site-header"><a class="wordmark" href="../../">MicroBlocks</a>'
            '<nav aria-label="Main navigation"><a href="../../">All boards</a></nav></header>\n'
            '<main class="install-guide"><h1>Install SmallVM: ' + name + '</h1>'
            '<p class="installation-method">' + escape(board['method']) + '</p>'
            '<p>' + escape(board['summary']) + '</p>'
            '<section aria-labelledby="steps"><h2 id="steps">Installation steps</h2><ol>' + steps + '</ol>'
            '<div class="guide-links">' + links + '</div></section>'
            '<section class="release-status" data-release-kind="' + release['kind'] + '" aria-labelledby="releases">'
            '<h2 id="releases">Release availability</h2><p>' + escape(release['note']) + '</p>'
            '<a class="release-link" href="' + escape(release['url'], quote=True) + '" target="_blank" rel="noopener noreferrer">'
            + escape(release['label']) + '</a><p class="review-date">Release links reviewed ' + escape(catalog['reviewed_on']) + '.</p></section>'
            '<a class="guide-editor" href="../../js-preview/' + board['id'] + '/index.html" target="_blank" rel="noopener">Open '
            + name + ' editor</a></main></body></html>\n')
        result[installation_url(board)] = html.encode()
    return result
