#!/usr/bin/env python3
"""Compile a real GP wake-word hat into SmallVM's native event scheduling."""
# SPDX-License-Identifier: MPL-2.0
def once(text,before,after):
 if text.count(before)!=1:raise ValueError('Changed GP wake-word anchor: '+before[:70])
 return text.replace(before,after)

def patch(name,payload):
 text=payload.decode('utf8')
 if name.endswith('/MicroBlocksCompiler.gp'):
  anchor="\t\t} ('whenBroadcastReceived' == op) {\n"
  text=once(text,anchor,"\t\t} ('p4WhenWakeWord' == op) {\n\t\t\taddAll result (instructionsForExpression this '_p4.wake.OkayNabu')\n\t\t\tadd result (array 'recvBroadcast' 1)\n\t\t\taddAll result (instructionsForCmdList this (nextBlock cmdOrReporter))\n"+anchor)
 elif name.endswith('/MicroBlocksRuntime.gp'):
  anchor="\tif ('whenBroadcastReceived' == op) { return 6 }"
  text=once(text,anchor,anchor+"\n\tif ('p4WhenWakeWord' == op) { return 6 }")
  anchor="(not (isOneOf op 'whenButtonPressed' 'whenBroadcastReceived'))"
  text=once(text,anchor,"(not (isOneOf op 'whenButtonPressed' 'whenBroadcastReceived' 'p4WhenWakeWord'))")
 return text.encode('utf8')
