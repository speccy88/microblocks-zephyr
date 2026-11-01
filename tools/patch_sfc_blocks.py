#!/usr/bin/env python3
"""Guarded opt-in native SFC forms for the pinned genuine GP compiler."""
# SPDX-License-Identifier: MPL-2.0
import json
from pathlib import Path
from sfc_branch_icons import gp_source, resources
from linux_editor_assets import package_metadata, replace_once


def patch_package(javascript, data, repo):
    source, match, metadata = package_metadata(javascript, data)
    packed, entries, changes = bytearray(), [], {}
    for item in metadata['files']:
        name = item['filename']
        payload = data[int(item['start']):int(item['end'])]
        original = payload
        if name == '/runtime/lib/MicroBlocksCompiler.gp':
            anchor = b"\t\t(array ' ' 'waitUntil'\t\t\t'wait until _' 'bool')"
            payload = replace_once(payload, anchor, anchor + b"\n\t\t'-'\n"
                b"\t\t(array ' ' 'sfcSequence' 'SFC sequence _' 'cmd')\n"
                b"\t\t(array ' ' 'sfcStep' 'step _ setup _ loop _' 'var cmd cmd' 'Step1')\n"
                b"\t\t(array ' ' 'sfcTransition' 'transition _' 'var' 'Transition1')\n"
                b"\t\t(array ' ' 'sfcAnd' 'parallel #SFC_AND_SPLIT# _ _ : branch _ : ...' 'cmd cmd cmd cmd cmd cmd')\n"
                b"\t\t(array ' ' 'sfcAndJoin' '#SFC_AND_JOIN# join all transition _' 'var' 'Join')\n"
                b"\t\t(array ' ' 'sfcOr' 'OR #SFC_OR_SPLIT# transition _ _ transition _ _ : transition _ _ : ...' 'var cmd var cmd var cmd var cmd var cmd var cmd' 'Choice1' nil 'Choice2' nil 'Choice3' nil 'Choice4' nil 'Choice5' nil 'Choice6')\n"
                b"\t\t(array ' ' 'sfcOrJoin' '#SFC_OR_JOIN# merge transition _' 'var' 'Merge')")
            anchor = b"\tif (isOneOf op '=' 'local') {"
            payload = replace_once(payload, anchor,
                b"\tif ('sfcSequence' == op) {\n\t\treturn (instructionsForSFCSequence this args cmd)\n"
                b"\t} (isOneOf op 'sfcStep' 'sfcTransition' 'sfcAnd' 'sfcOr' 'sfcAndJoin' 'sfcOrJoin') {\n"
                b"\t\terror 'SFC: step and transition blocks must be inside a sequence'\n"
                b"\t} (isOneOf op '=' 'local') {")
            payload = replace_once(payload, b"(isOneOf (primName cmd) 'v' '=' '+=')",
                b"(isOneOf (primName cmd) 'v' '=' '+=' 'sfcStep' 'sfcTransition' 'sfcAndJoin' 'sfcOrJoin')")
            payload += b'\n' + (repo/'web/sfc-native.gp').read_bytes()
        elif name == '/runtime/lib/MicroBlocksProject.gp':
            anchor = b"(isOneOf op 'v' '=' '+=')"
            if payload.count(anchor) != 3:
                raise ValueError('Changed shared-variable reference anchors')
            prefix = b"if (isOneOf op 'v' '=' '+=') {\n\t\t\t\tvarName = (first (argList b))"
            if payload.count(prefix) != 3: raise ValueError('Changed project variable-list anchors')
            payload = payload.replace(prefix, b"for varName (sfcVariableNames b) {")
            anchor = b'method loadFromString MicroBlocksProject s updateLibraries {\n'
            payload = replace_once(payload, anchor, anchor+b'\tsfcLiveClear (smallRuntime)\n')
        elif name == '/runtime/lib/PrettyPrinter.gp':
            # Generic GP printing puts a newline between adjacent command args;
            # that separates setup and loop on reload. Keep both in one command.
            anchor = b"\t} (prim == 'for') {"
            payload = replace_once(payload, anchor,
                b"\t} (prim == 'sfcStep') {\n"
                b"\t\tcontrol gen prim\n"
                b"\t\tprintValue this (getField block offset)\n"
                b"\t\tprintCmdList this (getField block (offset + 1)) true\n"
                b"\t\tprintCmdList this (getField block (offset + 2)) true\n"
                b"\t\tcrIfNeeded gen\n"
                b"\t} (isOneOf prim 'sfcAnd' 'sfcOr') {\n"
                b"\t\tcontrol gen prim\n"
                b"\t\tfor i (count (argList block)) {\n"
                b"\t\t\targ = (at (argList block) i)\n"
                b"\t\t\tif (and (prim == 'sfcOr') ((i % 2) == 1)) { printValue this arg } else { printCmdList this arg true }\n"
                b"\t\t}\n\t\tcrIfNeeded gen\n" + anchor)
        elif name == '/runtime/lib/Block.gp':
            anchor = b'method labelText Block aString {\n'
            payload = replace_once(payload, anchor, anchor+b"\taString = (sfcBarSVG aString)\n")
            payload = replace_once(payload, b'originalColor p4MediaID p4MediaView\n',
                b'originalColor p4MediaID p4MediaView sfcLiveActive\n')
            payload = replace_once(payload, b'drawBlock aShapeMaker r color',
                b'drawBlock aShapeMaker r (sfcBlockDisplayColor this)')
            payload = replace_once(payload, b'drawBlockWithCommandSlots aShapeMaker r commandSlots color',
                b'drawBlockWithCommandSlots aShapeMaker r commandSlots (sfcBlockDisplayColor this)')
        elif name == '/runtime/lib/MicroBlocksScripter.gp':
            anchor = b'method step MicroBlocksScripter {\n'
            payload = replace_once(payload, anchor, anchor+b'\tsfcLivePoll (smallRuntime)\n')
        elif name == '/runtime/lib/MicroBlocksRuntime.gp':
            payload = replace_once(payload, b'compiler api codeStoreFull\n', b'compiler api codeStoreFull sfcWorkerSource sfcWorkerPlans\n')
            anchor = b'method assignFunctionIDs SmallRuntime {\n'
            payload = replace_once(payload, anchor, anchor+b'\tsfcPrepareWorkers this\n')
            anchor = b'method stopRunningChunk SmallRuntime chunkID {\n'
            payload = replace_once(payload, anchor, anchor+b'\tsfcCancelOwner this chunkID\n')
            anchor = b'method clearRunningHighlights SmallRuntime {\n'
            payload = replace_once(payload, anchor, anchor+b'\tsfcLiveClear this\n')
            anchor = b'method updateRunning SmallRuntime chunkID runFlag {\n'
            payload = replace_once(payload, anchor, anchor+b'\tif runFlag { sfcLiveChunkStarted this chunkID } else { sfcLiveChunkStopped this chunkID }\n')
            anchor = b'\t\tnop // formerly used by the local IDE httpServer\n\t\t// varValueReceived'
            payload = replace_once(payload, anchor,
                b'\t\tsfcLiveReceive this (byteAt msg 3) (returnedValue this msg) (msecsSinceStart)\n\t\t// varValueReceived')
        elif name == '/runtime/lib/zzzMicroBlocksPatches.gp':
            payload += b'\n' + (repo/'web/sfc-live.gp').read_bytes() + b'\n' + (repo/'web/sfc-branches.gp').read_bytes() + b'\n' + gp_source(repo)
        if payload != original:
            changes[name] = True
        start = len(packed)
        packed.extend(payload)
        entries.append(dict(filename=name, start=start, end=len(packed)))
    if set(changes) != {'/runtime/lib/MicroBlocksCompiler.gp','/runtime/lib/MicroBlocksProject.gp','/runtime/lib/PrettyPrinter.gp',
        '/runtime/lib/Block.gp','/runtime/lib/MicroBlocksScripter.gp','/runtime/lib/MicroBlocksRuntime.gp','/runtime/lib/zzzMicroBlocksPatches.gp'}:
        raise ValueError('Missing native SFC compiler/project sources')
    names={item['filename'] for item in entries}
    for name,payload in sorted(resources(repo).items()):
        if name in names:raise ValueError('SFC icon resource already exists: '+name)
        start=len(packed);packed.extend(payload)
        entries.append(dict(filename=name,start=start,end=len(packed)))
    table = json.dumps(dict(files=entries,remote_package_size=len(packed)),separators=(',',':'))
    return (source[:match.start(1)]+table+source[match.end(1):]).encode('utf8'), bytes(packed)
