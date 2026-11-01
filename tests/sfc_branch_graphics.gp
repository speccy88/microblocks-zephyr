// SPDX-License-Identifier: MPL-2.0 - offline native GP spec/serialization checks.
to sfcBranchExpect test label {
	if (not test) { error (join 'SFC graphics: ' label) }
	add (global 'sfcBranchChecks') label
}
to sfcHeadlessChecks p r {
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
