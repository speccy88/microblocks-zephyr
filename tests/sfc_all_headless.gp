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

to sfcSerialVisualChecks p r {
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

// SPDX-License-Identifier: MPL-2.0 - offline native GP spec/serialization checks.
to sfcBranchExpect test label {
	if (not test) { error (join 'SFC graphics: ' label) }
	add (global 'sfcBranchChecks') label
}
to sfcBranchVisualChecks p r {
	setGlobal 'sfcBranchChecks' (list)
	clear (authoringSpecs)
	addSpecs (authoringSpecs) (microBlocksSpecs (initialize (new 'SmallCompiler')))
	for op (array 'sfcAnd' 'sfcOr') {
		spec = (specForOp (authoringSpecs) op)
		sfcBranchExpect (repeatLastSpec spec) (join op ' uses native extensible slots')
		expected = 6
		if (op == 'sfcOr') { expected = 12 }
		sfcBranchExpect ((slotCount spec) == expected) (join op ' declares six branch slots')
		if (op == 'sfcOr') {
			for i (range 1 11 2) {
				info = (slotInfoForIndex spec i)
				sfcBranchExpect (and ((first info) == 'var') (isClass (at info 2) 'String')) (join 'OR guard slot ' i ' has a valid shared-variable template')
			}
		}
	}
	for token (array '#SFC_OR_SPLIT#' '#SFC_OR_JOIN#' '#SFC_AND_SPLIT#' '#SFC_AND_JOIN#') {
		svg = (sfcBarSVG token)
		sfcBranchExpect (beginsWith svg '#SVG#sfc-') (join token ' resolves to a named native SVG label')
	}
	sfcBranchExpect (saveLoadTest p) 'native branch counts and shared variables save/reload'
	sfcBranchExpect (not (contains (unusedGlobals p) 'Choice2')) 'second OR guard is tracked as a used MicroBlocks variable'
	// Build the precise stop requests without opening a transport or sending them.
	for name (allVariableNames p) { indexForVar p name }
	owner = (new 'Block')
	setField owner 'expression' (last (first (scripts (main p))))
	atPut (getField r 'chunkIDs') owner (array 128 nil 4 '' false)
	commands = (sfcCancelPlan r 128)
	stops = 0
	sets = 0
	for command commands {
		if ((first command) == 'stop') { stops += 1 }
		if ((first command) == 'set') { sets += 1 }
	}
	workerCount = (at (first (sfcPlansForReport r)) 'worker_count')
	sfcBranchExpect (stops == workerCount) 'stopping owner targets all owned worker chunks'
	sfcBranchExpect (sets == (workerCount + 3)) 'stop requests clear flags, run state and status'
	sfcBranchExpect ((count (sfcCancelPlan r 222)) == 0) 'unrelated script stop cannot cancel SFC workers'
	before = (codeString p)
	assignFunctionIDs r
	sfcBranchExpect (before == (codeString p)) 'repeated compilation keeps the generated worker library stable'
	reserved = (libraryNamed p '_SFC workers')
	userSource = (sfcUserSource p reserved)
	extra = (loadFromCmds (newMicroBlocksModule) (parse (join 'module Extra Control' (newline) 'variables UserFlag')))
	atPut (getField p 'libraries') 'Extra' extra
	sfcBranchExpect (userSource != (sfcUserSource p reserved)) 'library-only edits invalidate the worker cache'
	remove (getField p 'libraries') 'Extra'
	return (global 'sfcBranchChecks')
}

to sfcHeadlessChecks p r {
 checks = (sfcSerialVisualChecks p r)
 addAll checks (sfcBranchVisualChecks p r)
 return checks
}
