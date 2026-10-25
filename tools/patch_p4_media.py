#!/usr/bin/env python3
"""Small guarded source patches to the pinned, genuine GP editor."""
# SPDX-License-Identifier: MPL-2.0
from pathlib import Path
def replace_once(source,before,after):
 if source.count(before)!=1:raise ValueError('Changed GP inline-media anchor: '+before[:80])
 return source.replace(before,after)

def patch_source(name,payload,repo):
 text=payload.decode('utf8')
 if name.endswith('/Block.gp'):
  text=replace_once(text,'function isAlternative layoutNeeded pathCache cacheW cacheH originalColor\n',
   'function isAlternative layoutNeeded pathCache cacheW cacheH originalColor p4MediaID p4MediaView\n')
  text=replace_once(text,'method fixLayout Block {\n',
   "method fixLayout Block {\n\tif (notNil p4MediaView) { p4Size p4MediaView }\n")
 elif name.endswith('/MicroBlocksScripter.gp'):
  text=replace_once(text,'method step MicroBlocksScripter {\n','method step MicroBlocksScripter {\n\tp4MediaStep this\n')
 elif name.endswith('/MicroBlocksCompiler.gp'):
  text=replace_once(text,'return (instructionsForFunctionCall this op args false)',
   'return (p4MediaTrace this expr (instructionsForFunctionCall this op args false))')
  text=replace_once(text,'return (primitive this op args false)',
   'return (p4MediaTrace this expr (primitive this op args false))')
 elif name.endswith('/MicroBlocksRuntime.gp'):
  for anchor in ['method startAll SmallRuntime {\n','method evalOnBoard SmallRuntime aBlock showBytes {\n']:
   text=replace_once(text,anchor,anchor+"\tnotify api 'p4.media.run' (array)\n")
 elif name.endswith('/MicroBlocksAPI.gp'):
  anchor="} (endPoint == 'project.save') {"
  api="""} (endPoint == 'p4.media.enable') {
        session = (at params 1)
        if (or (session < 0) (session > 536870911)) { session = 0 }
        setGlobal 'p4MediaSession' session
        recompileNeeded runtime
        if (session > 0) { saveAllChunks runtime true }
        respondAPIRequest this id true
    } (endPoint == 'p4.media.layout') {
        p4MediaStep scripter
        respondAPIRequest this id (p4MediaLayout scripter)
    } (endPoint == 'p4.media.result') {
        respondAPIRequest this id (p4MediaResult (at params 1) (at params 2) (at params 3) (at params 4) (at params 5))
    } (endPoint == 'p4.media.toggle') {
        respondAPIRequest this id (p4MediaToggle (at params 1) (at params 2))
    } (endPoint == 'p4.media.expire') {
        respondAPIRequest this id (p4MediaExpire (at params 1))
    """
  text=replace_once(text,anchor,api+anchor)
 elif name.endswith('/zzzMicroBlocksPatches.gp'):
  text+='\n'+(repo/'web/p4-media.gp').read_text(encoding='utf8')
 return text.encode('utf8')
