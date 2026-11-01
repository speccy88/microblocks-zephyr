"""Native GP label icons: a single OR bar and double AND bars."""
import json

def resource_name(token):
    return token.strip('#').lower().replace('_','-')


def icons(repo):
    data=json.loads((repo/'web/sfc-bars.json').read_text())
    result={}
    for token,item in data.items():
        # GP SVGReader treats later M commands in one path as lineTo. Separate
        # path elements prevent diagonal connectors between Grafcet bar strokes.
        paths=''.join(f'<path d="M{x1},{y1}L{x2},{y2}" fill="none" stroke="#ffffff" stroke-width="2"/>' for x1,y1,x2,y2 in item['lines'])
        result[token]='<svg xmlns="http://www.w3.org/2000/svg" width="36" height="18" viewBox="0 0 36 18">'+paths+'</svg>'
    return result

def resources(repo):
    return {'/img/'+resource_name(token)+'.svg':svg.encode('utf8') for token,svg in icons(repo).items()}


def gp_source(repo):
    lines=['// SPDX-License-Identifier: MPL-2.0','to sfcBarSVG token {']
    for token in icons(repo):lines.append(" if (token == '"+token+"') { return '#SVG#"+resource_name(token)+"' }")
    lines+=[' return token','}']
    return ('\n'.join(lines)+'\n').encode('utf8')
