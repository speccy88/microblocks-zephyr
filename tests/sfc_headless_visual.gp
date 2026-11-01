// SPDX-License-Identifier: MPL-2.0
// Genuine GP classes and live-state code, offline; no browser or serial transport.
to sfcExpect condition message {
	if (not condition) { error (join 'SFC check: ' message) }
	add (global 'sfcCheckResults') message
}

to sfcTestBlock name {
	b = (new 'Block')
	setField b 'expression' (newCommand 'sfcStep' name nil nil)
	setField b 'type' 'command'
	setField b 'color' (color 200 140 20)
	setField b 'morph' (newMorph b)
	return b
}

to sfcHeadlessChecks p r {
	setGlobal 'sfcCheckResults' (list)
	setGlobal 'scale' 1
	before = (codeString p)
	b1 = (sfcTestBlock 'Step1')
	b2 = (sfcTestBlock 'Step2')
	steps = (list)
	for cmd (allBlocks (last (first (scripts (main p)))) ) {
		if ('sfcStep' == (primName cmd)) { add steps cmd }
	}
	setField b1 'expression' (at steps 1)
	setField b2 'expression' (at steps 2)
	flags = (newArray 256 false)
	atPut flags 129 true
	atPut flags 130 true
	setField r 'chunkRunning' flags
	records = (array (array b1 0 128) (array b2 1 129))
	sfcLiveBind r records 0
	sfcExpect ((count (sfcLiveRequests r 0)) == 2) 'requests shared step variables'
	sfcLiveReceive r 0 true 10
	sfcLiveReceive r 1 true 10
	sfcExpect (and (getField b1 'sfcLiveActive') (getField b2 'sfcLiveActive')) 'simultaneous active steps are all visible'
	sfcExpect ((green (sfcBlockDisplayColor b1)) == 190) 'active step uses green display color'
	sfcExpect ((red (getField b1 'color')) == 200) 'original block color is preserved'
	sfcLiveChunkStopped r 128
	sfcExpect (and (not (getField b1 'sfcLiveActive')) (getField b2 'sfcLiveActive')) 'stopping one sequence preserves another active indication'
	sfcLiveChunkStarted r 128
	sfcExpect ((count (sfcLiveRequests r 100)) == 0) 'polling rate is bounded'
	sfcLiveRequests r 250
	sfcLiveReceive r 0 false 260
	sfcExpect (not (getField b1 'sfcLiveActive')) 'false variable clears active indication'
	sfcExpect ((red (sfcBlockDisplayColor b1)) == 200) 'inactive display restores original color'
	sfcExpect (not (sfcLiveReceive r 99 true 270)) 'unrequested replies cannot activate steps'
	sfcLiveExpire r 1520
	sfcExpect (not (getField b2 'sfcLiveActive')) 'stale values expire'
	sfcLiveRequests r 1600
	sfcLiveReceive r 1 true 1610
	sfcLiveChunkStopped r 129
	sfcExpect (not (getField b2 'sfcLiveActive')) 'stopped chunk clears its indication immediately'
	sfcExpect (not (contains (sfcLiveRequests r 1900) 1)) 'delayed generic running highlight cannot reactivate a stopped step'
	sfcLiveChunkStarted r 129
	sfcLiveRequests r 2200
	sfcLiveReceive r 1 true 2210
	sfcExpect (getField b2 'sfcLiveActive') 'new chunk start can activate fresh state'
	sfcLiveBind r (array (array b1 0 128)) 2220
	sfcExpect (not (getField b2 'sfcLiveActive')) 'removed blocks lose live indication'
	sfcLiveClear r
	sfcExpect (not (sfcLiveReceive r 0 true 2230)) 'late replies after stop are ignored'
	sfcExpect (before == (codeString p)) 'live display state never enters saved project'
	// Exercise the same shape recorder used by GP's normal block drawing.
	setWidth (bounds (morph b1)) 180
	setHeight (bounds (morph b1)) 80
	sfcSetBlockActive b1 true
	sm = (newShapeMakerForPathRecording)
	drawShape b1 sm
	sfcExpect ((count (recordedPaths sm)) > 0) 'real GP shape recorder draws active native block'
	sfcSetBlockActive b1 false
	sfcLiveClear r
	now = (msecsSinceStart)
	sfcLiveBind r records now
	sfcLiveRequests r now
	handleMessage r (toBinaryData (array 251 21 0 2 0 3 1))
	handleMessage r (toBinaryData (array 251 21 1 2 0 3 1))
	sfcExpect (and (getField b1 'sfcLiveActive') (getField b2 'sfcLiveActive')) 'real GP variable-message handler updates simultaneous steps'
	sfcLiveClear r
	handleMessage r (toBinaryData (array 251 21 0 2 0 3 1))
	sfcExpect (not (getField b1 'sfcLiveActive')) 'real GP handler ignores delayed reply after clear'
	sfcLiveBind r records 0
	sfcLiveRequests r 0
	sfcLiveReceive r 0 1 10
	sfcExpect (not (getField b1 'sfcLiveActive')) 'numeric one never shows an active step'
	sfcLiveClear r
	many = (list)
	for i 6 { add many (array (sfcTestBlock (join 'Test' i)) (i - 1) 128) }
	sfcLiveBind r many 0
	sfcExpect ((count (sfcLiveRequests r 0)) == 4) 'read budget is four requests per polling interval'
	sfcExpect ((count (sfcLiveRequests r 250)) == 2) 'round robin reaches remaining variables without duplicating pending reads'
	sfcLiveClear r
	return (global 'sfcCheckResults')
}
