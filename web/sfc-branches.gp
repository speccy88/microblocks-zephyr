// SPDX-License-Identifier: MPL-2.0
// Structured graph lowering and ordinary SmallVM cooperative action workers.

to sfcHasBranches cmd {
	for b (allBlocks cmd) { if (isOneOf (primName b) 'sfcAnd' 'sfcOr') { return true } }
	return false
}
to sfcV name { return (newReporter 'v' name) }
to sfcTrue name { return (newReporter '==' (sfcV name) true) }
to sfcAll terms {
	if (isEmpty terms) { return true }
	r = (first terms)
	for i (range 2 (count terms)) { r = (newReporter 'and' r (at terms i)) }
	return r
}
to sfcAny terms {
	if (isEmpty terms) { return false }
	r = (first terms)
	for i (range 2 (count terms)) { r = (newReporter 'or' r (at terms i)) }
	return r
}
to sfcCommands commands {
	if (isEmpty commands) { return nil }
	for i (range 1 ((count commands) - 1)) { setField (at commands i) 'nextBlock' (at commands (i + 1)) }
	return (first commands)
}
to sfcSet name value { return (newCommand '=' name value) }
to sfcTest mask bits { return (newReporter '==' (newReporter '&' mask bits) bits) }
to sfcAddMask name bits { return (sfcSet name (newReporter '|' (sfcV name) bits)) }
to sfcBit id { return (1 << (id - 1)) }

method sfcBranchStep SmallCompiler graph cmd {
	if (or (isNil cmd) ('sfcStep' != (primName cmd))) { error 'SFC: a branch path must begin/end with a step' }
	a = (argList cmd)
	if ((count a) != 3) { error 'SFC: step needs variable, setup and loop' }
	for i (array 2 3) {
		for action (allBlocks (at a i)) {
			if (beginsWith (primName action) 'sfc') { error 'SFC: flow blocks cannot be nested inside setup/loop actions' }
			if (isOneOf (primName action) 'return' 'stopTask' 'stopAll') { error 'SFC: actions cannot directly return or stop their worker tasks' }
		}
	}
	name = (sfcSharedVariable this (first a))
	for step (at graph 'steps') { if ((at step 2) == name) { error 'SFC: duplicate step variable' } }
	id = ((count (at graph 'steps')) + 1)
	if (id > 8) { error 'SFC: this cooperative worker prototype supports at most eight steps per chart' }
	add (at graph 'steps') (array id name (at a 2) (at a 3))
	return id
}

method sfcBranchEdge SmallCompiler graph from to guards {
	if ((count (at graph 'edges')) >= 24) { error 'SFC: too many transition edges' }
	for name guards {
		sfcSharedVariable this name
		if (not (contains (at graph 'guards') name)) { add (at graph 'guards') name }
	}
	if ((count (at graph 'guards')) > 24) { error 'SFC: too many transition variables' }
	add (at graph 'edges') (array from to (toArray guards))
}

method sfcBranchFork SmallCompiler graph source fork common {
	parallel = ('sfcAnd' == (primName fork))
	join = (nextBlock fork)
	if (isNil join) { error 'SFC: split requires a matching join' }
	expected = 'sfcOrJoin'
	if parallel { expected = 'sfcAndJoin' }
	if ((primName join) != expected) { error 'SFC: mismatched split/join type' }
	if ((count (argList join)) != 1) { error 'SFC: join needs one shared transition variable' }
	guard = (sfcSharedVariable this (first (argList join)))
	fa = (argList fork)
	wrappers = (list)
	if parallel {
		if (or ((count fa) < 2) ((count fa) > 6)) { error 'SFC: choose two through six parallel branches' }
		for body fa { add wrappers (newCommand 'sfcBranch' body) }
	} else {
		if (or ((count fa) < 4) ((count fa) > 12) (((count fa) % 2) != 0)) { error 'SFC: choose two through six guarded alternatives' }
		for i (range 1 (count fa) 2) { add wrappers (newCommand 'sfcAlternative' (at fa i) (at fa (i + 1))) }
	}
	branch = (sfcCommands wrappers)
	entries = (list)
	finals = 0
	while (notNil branch) {
		ba = (argList branch)
		conditions = (copy common)
		if parallel {
			if (or ('sfcBranch' != (primName branch)) ((count ba) != 1)) { error 'SFC: AND split accepts parallel branch blocks' }
			path = (first ba)
		} else {
			if (or ('sfcAlternative' != (primName branch)) ((count ba) != 2)) { error 'SFC: OR split accepts guarded alternatives' }
			add conditions (sfcSharedVariable this (first ba))
			path = (at ba 2)
		}
		ends = (sfcBranchPath this graph path true)
		add entries (array (sfcBit (first ends)) conditions)
		finals = (finals | (sfcBit (at ends 2)))
		branch = (nextBlock branch)
	}
	if (or ((count entries) < 2) ((count entries) > 6)) { error 'SFC: choose two through six branches' }
	target = (nextBlock join)
	targetID = (sfcBranchStep this graph target)
	if parallel {
		if (isEmpty common) { error 'SFC: AND split needs a preceding shared transition' }
		firstMask = 0
		for entry entries { firstMask = (firstMask | (first entry)) }
		sfcBranchEdge this graph (sfcBit source) firstMask common
		sfcBranchEdge this graph finals (sfcBit targetID) (list guard)
	} else {
		for entry entries { sfcBranchEdge this graph (sfcBit source) (first entry) (at entry 2) }
		for step (at graph 'steps') {
			bit = (sfcBit (first step))
			if ((finals & bit) != 0) { sfcBranchEdge this graph bit (sfcBit targetID) (list guard) }
		}
	}
	return (array targetID target)
}

method sfcBranchPath SmallCompiler graph cmd branchPath {
	firstID = (sfcBranchStep this graph cmd)
	current = firstID
	while (notNil cmd) {
		next = (nextBlock cmd)
		if (isNil next) {
			if (not branchPath) { error 'SFC: top-level terminal step needs a transition' }
			return (array firstID current)
		}
		common = (list)
		if ('sfcTransition' == (primName next)) {
			if ((count (argList next)) != 1) { error 'SFC: transition needs one shared variable' }
			add common (sfcSharedVariable this (first (argList next)))
			next = (nextBlock next)
			if (isNil next) {
				if branchPath { error 'SFC: branch must finish on an active step before the join' }
				sfcBranchEdge this graph (sfcBit current) 0 common
				return (array firstID current)
			}
		}
		if ('sfcStep' == (primName next)) {
			if (isEmpty common) { error 'SFC: adjacent steps need a transition' }
			target = (sfcBranchStep this graph next)
			sfcBranchEdge this graph (sfcBit current) (sfcBit target) common
			current = target
			cmd = next
		} (isOneOf (primName next) 'sfcAnd' 'sfcOr') {
			joined = (sfcBranchFork this graph current next common)
			current = (first joined)
			cmd = (at joined 2)
		} else { error 'SFC: ordinary commands belong inside setup/loop; invalid flow structure' }
	}
	return (array firstID current)
}

method sfcBranchGraph SmallCompiler cmd {
	if ((count (argList cmd)) != 1) { error 'SFC: sequence needs one command section' }
	graph = (dictionary)
	atPut graph 'steps' (list)
	atPut graph 'guards' (list)
	atPut graph 'edges' (list)
	ends = (sfcBranchPath this graph (first (argList cmd)) false)
	atPut graph 'initial' (sfcBit (first ends))
	for step (at graph 'steps') {
		if (contains (at graph 'guards') (at step 2)) { error 'SFC: step and transition variables must be disjoint' }
	}
	return graph
}

to sfcPrivate prefix field id {
	if (isNil id) { return (join prefix field) }
	return (join prefix field id)
}
to sfcStepTerms graph prefix field mask {
	terms = (list)
	for step (at graph 'steps') {
		if ((mask & (sfcBit (first step))) != 0) { add terms (sfcTrue (sfcPrivate prefix field (first step))) }
	}
	return terms
}
to sfcPublish graph mask {
	commands = (list)
	for step (at graph 'steps') { add commands (sfcSet (at step 2) (sfcTest mask (sfcBit (first step)))) }
	return (sfcCommands commands)
}
to sfcElapsed start { return (newReporter '&' (newReporter '-' (newReporter 'millisOp') (sfcV start)) 1073741823) }
to sfcDeadlineWait condition {
	return (sfcCommands (list (newCommand 'local' '_sfcTimer' (newReporter 'millisOp'))
		(newCommand 'repeatUntil' (newReporter 'or' condition (newReporter '>=' (sfcElapsed '_sfcTimer') 500)) (newCommand 'waitMillis' 1))))
}

to sfcWorkerBody graph prefix step {
	id = (first step)
	run = (sfcPrivate prefix 'run')
	gate = (sfcPrivate prefix 'gate')
	ready = (sfcPrivate prefix 'ready' id)
	setup = (sfcPrivate prefix 'setup' id)
	request = (sfcPrivate prefix 'request' id)
	ack = (sfcPrivate prefix 'ack' id)
	done = (sfcPrivate prefix 'done' id)
	setupBody = (sfcCommands (list (newCommand 'repeat' 1 (at step 3)) (sfcSet setup true)))
	actions = (sfcCommands (list
		(newCommand 'if' (newReporter 'not' (sfcTrue setup)) setupBody)
		(newCommand 'if' (sfcTrue request) (sfcSet ack true) true (newCommand 'repeat' 1 (at step 4)))))
	body = (sfcCommands (list (newCommand 'if' (sfcTest (sfcV (sfcPrivate prefix 'active')) (sfcBit id)) actions) (newCommand 'waitMillis' 1)))
	return (sfcCommands (list (sfcSet ready true)
		(newCommand 'waitUntil' (newReporter 'or' (sfcTrue gate) (newReporter 'not' (sfcTrue run))))
		(newCommand 'repeatUntil' (newReporter 'not' (sfcTrue run)) body)
		(sfcSet done true) (newCommand 'stopTask')))
}

to sfcInitBody graph prefix {
	commands = (list)
	run = (sfcPrivate prefix 'run')
	status = (sfcPrivate prefix 'status')
	add commands (newCommand 'if' (newReporter 'or' (sfcTrue run) (newReporter '==' (sfcV status) -2)) (newCommand 'return' false))
	add commands (sfcSet status 1)
	add commands (sfcSet run true)
	add commands (sfcSet (sfcPrivate prefix 'active') 0)
	add commands (sfcSet (sfcPrivate prefix 'gate') false)
	for step (at graph 'steps') {
		add commands (sfcSet (at step 2) false)
		for field (array 'ready' 'setup' 'request' 'ack' 'done') { add commands (sfcSet (sfcPrivate prefix field (first step)) false) }
	}
	for step (at graph 'steps') { add commands (newCommand 'sendBroadcast' (sfcPrivate prefix 'worker' (first step))) }
	ready = (sfcAll (sfcStepTerms graph prefix 'ready' 65535))
	add commands (newCommand 'repeat' 1 (sfcDeadlineWait ready))
	failed = (sfcCommands (list (sfcSet run false) (sfcSet (sfcPrivate prefix 'gate') true) (sfcSet status -1) (newCommand 'return' false)))
	add commands (newCommand 'if' (newReporter 'not' ready) failed)
	add commands (newCommand 'return' true)
	return (sfcCommands commands)
}

to sfcFinishBody graph prefix {
	run = (sfcPrivate prefix 'run')
	status = (sfcPrivate prefix 'status')
	terms = (list)
	for step (at graph 'steps') {
		id = (first step)
		add terms (newReporter 'or' (newReporter 'not' (sfcTrue (sfcPrivate prefix 'ready' id))) (sfcTrue (sfcPrivate prefix 'done' id)))
	}
	done = (sfcAll terms)
	return (sfcCommands (list (sfcSet run false) (sfcSet (sfcPrivate prefix 'gate') true)
		(newCommand 'repeat' 1 (sfcPublish graph 0)) (sfcSet (sfcPrivate prefix 'active') 0)
		(newCommand 'repeat' 1 (sfcDeadlineWait done))
		(newCommand 'if' (newReporter 'not' done) (sfcCommands (list (sfcSet status -2) (newCommand 'return' false))))
		// A done store can be the last opcode in a Linux VM slice. Let every
		// worker return before a caller can immediately broadcast the next cycle.
		(newCommand 'waitMillis' 1)
		(newCommand 'if' (newReporter '==' (sfcV 'dummy') -3) (sfcSet status -3))
		(newCommand 'return' true)))
}

to sfcOwnerBody graph prefix {
	active = '_sfcActive'
	consumed = '_sfcConsumed'
	activated = '_sfcActivated'
	inputs = '_sfcInputs'
	selected = '_sfcSelected'
	run = (sfcPrivate prefix 'run')
	status = (sfcPrivate prefix 'status')
	commands = (list)
	failed = (sfcCommands (list (newCommand (sfcPrivate prefix 'finish') 0) (newCommand 'return' false)))
	add commands (newCommand 'if' (newReporter 'not' (newReporter (sfcPrivate prefix 'init') 0)) failed)
	for name (array active consumed activated inputs selected) { add commands (newCommand 'local' name 0) }
	add commands (sfcSet active (at graph 'initial'))
	add commands (newCommand 'repeat' 1 (sfcPublish graph (sfcV active)))
	add commands (sfcSet (sfcPrivate prefix 'active') (sfcV active))
	add commands (sfcSet (sfcPrivate prefix 'gate') true)
	add commands (sfcSet status 2)
	scan = (list)
	add scan (sfcSet inputs (newReporter (sfcPrivate prefix 'inputs') 0))
	add scan (sfcSet selected (newReporter (sfcPrivate prefix 'select') (sfcV active) (sfcV inputs)))
	add scan (sfcSet consumed (newReporter '&' (sfcV selected) 255))
	add scan (sfcSet activated (newReporter '&' (newReporter '>>' (sfcV selected) 8) 255))
	for step (at graph 'steps') {
		id = (first step)
		add scan (newCommand 'if' (sfcTest (sfcV consumed) (sfcBit id)) (sfcSet (sfcPrivate prefix 'request' id) true))
	}
	acks = (list)
	for step (at graph 'steps') {
		id = (first step)
		add acks (newReporter 'or' (newReporter 'not' (sfcTest (sfcV consumed) (sfcBit id))) (sfcTrue (sfcPrivate prefix 'ack' id)))
	}
	add scan (newCommand 'waitUntil' (newReporter 'or' (sfcAll acks) (newReporter 'not' (sfcTrue run))))
	add scan (newCommand 'if' (newReporter 'not' (sfcTrue run)) (sfcCommands (list
		(newCommand (sfcPrivate prefix 'finish') -3)
		(newCommand 'return' false))))
	remaining = (newReporter '&' (sfcV active) (newReporter '-' 65535 (sfcV consumed)))
	add scan (sfcSet active (newReporter '|' remaining (sfcV activated)))
	add scan (newCommand 'repeat' 1 (sfcPublish graph (sfcV active)))
	add scan (sfcSet (sfcPrivate prefix 'active') (sfcV active))
	add scan (newCommand 'waitMillis' 1)
	add commands (newCommand 'repeatUntil' (newReporter 'or' (newReporter '==' (sfcV active) 0) (newReporter 'not' (sfcTrue run))) (sfcCommands scan))
	add commands (newCommand 'if' (newReporter 'not' (sfcTrue run)) (sfcCommands (list
		(newCommand (sfcPrivate prefix 'finish') -3)
		(newCommand 'return' false))))
	add commands (newCommand 'if' (newReporter 'not' (newReporter (sfcPrivate prefix 'finish') 0)) (newCommand 'return' false))
	add commands (sfcSet status 0)
	add commands (newCommand 'return' true)
	return (sfcCommands commands)
}

to sfcInputsBody graph {
	inputs = '_sfcInputs'
	commands = (list (newCommand 'local' inputs 0))
	for i (count (at graph 'guards')) {
		add commands (newCommand 'if' (sfcTrue (at (at graph 'guards') i)) (sfcAddMask inputs (sfcBit i)))
	}
	add commands (newCommand 'return' (sfcV inputs))
	return (sfcCommands commands)
}

to sfcSelectBody graph prefix {
	consumed = '_sfcUsed'
	activated = '_sfcTargets'
	commands = (list (newCommand 'local' consumed 0) (newCommand 'local' activated 0))
	for edge (at graph 'edges') {
		from = (first edge)
		guardMask = 0
		for guard (at edge 3) { guardMask = (guardMask | (sfcBit (indexOf (at graph 'guards') guard))) }
		terms = (sfcStepTerms graph prefix 'setup' from)
		add terms (sfcTest (sfcV 'activeMask') from)
		add terms (newReporter '==' (newReporter '&' (sfcV consumed) from) 0)
		add terms (sfcTest (sfcV 'inputMask') guardMask)
		body = (sfcCommands (list (sfcAddMask consumed from) (sfcAddMask activated (at edge 2))))
		add commands (newCommand 'if' (sfcAll terms) body)
	}
	add commands (newCommand 'return' (newReporter '|' (sfcV consumed) (newReporter '<<' (sfcV activated) 8)))
	return (sfcCommands commands)
}

to sfcFunctionText name body worker parameters {
	args = ' dummy'
	if worker { args = '' }
	if (notNil parameters) { args = (join ' ' parameters) }
	return (join 'to ' name args ' {' (newline) (prettyPrintList (new 'PrettyPrinter') body) '}' (newline))
}

to sfcVariableNames cmd {
	op = (primName cmd)
	args = (argList cmd)
	result = (list)
	if (isOneOf op 'v' '=' '+=' 'sfcStep' 'sfcTransition' 'sfcAndJoin' 'sfcOrJoin') {
		if (notEmpty args) { add result (first args) }
	} ('sfcOr' == op) {
		for i (range 1 (count args) 2) { add result (at args i) }
	}
	for i (count result) {
		name = (at result i)
		if (and (isClass name 'Reporter') ('v' == (primName name))) { atPut result i (first (argList name)) }
	}
	return result
}

method sfcPrepareWorkers SmallRuntime {
	p = (project scripter)
	roots = (list)
	rootCount = 0
	for entry (scripts (main p)) {
		body = (last entry)
		if (beginsWith (primName body) 'when') { rootCount += 1 }
		for cmd (allBlocks body) {
			if (and ('sfcSequence' == (primName cmd)) (sfcHasBranches cmd)) { add roots cmd }
		}
	}
	for func (allFunctions p) {
		if (sfcHasBranches (cmdList func)) { error 'SFC: branch charts must be top-level scripts; worker actions cannot capture function arguments' }
	}
	reserved = (libraryNamed p '_SFC workers')
	source = (sfcUserSource p reserved)
	if (and (source == sfcWorkerSource) (notNil sfcWorkerPlans) ((count roots) == (count sfcWorkerPlans))) {
		same = true
		for i (count roots) { if (not ((at roots i) === (first (at sfcWorkerPlans i)))) { same = false } }
		if same { return }
	}
	if (isEmpty roots) { sfcWorkerPlans = (list); sfcWorkerSource = source; return }
	if (and (notNil reserved) ((description reserved) != 'Generated cooperative SFC workers v1')) { error 'SFC: reserved worker library name already belongs to user data' }
	plans = (list)
	definitions = (list)
	variables = (list)
	workerCount = 0
	compiler = (initialize (new 'SmallCompiler'))
	for i (count roots) {
		cmd = (at roots i)
		graph = (sfcBranchGraph compiler cmd)
		prefix = (join '_sfc' i '_')
		workerCount += (count (at graph 'steps'))
		add plans (array cmd graph prefix)
		for field (array 'run' 'gate' 'active' 'status') { add variables (sfcPrivate prefix field) }
		for step (at graph 'steps') {
			for field (array 'ready' 'setup' 'request' 'ack' 'done') { add variables (sfcPrivate prefix field (first step)) }
			add definitions (sfcFunctionText (sfcPrivate prefix 'worker' (first step)) (sfcWorkerBody graph prefix step) true)
		}
		add definitions (sfcFunctionText (sfcPrivate prefix 'init') (sfcInitBody graph prefix) false)
		add definitions (sfcFunctionText (sfcPrivate prefix 'finish') (sfcFinishBody graph prefix) false)
		add definitions (sfcFunctionText (sfcPrivate prefix 'inputs') (sfcInputsBody graph) false)
		add definitions (sfcFunctionText (sfcPrivate prefix 'select') (sfcSelectBody graph prefix) false 'activeMask inputMask')
		add definitions (sfcFunctionText (sfcPrivate prefix 'owner') (sfcOwnerBody graph prefix) false)
	}
	if (or (workerCount > 8) ((workerCount + rootCount) > 10)) { error 'SFC: conservative task budget exceeded (eight workers, ten pinned VM tasks including script owners)' }
	// Step state has one owner across charts; guards may intentionally be shared.
	stepNames = (list)
	guardNames = (list)
	for plan plans { addAll guardNames (at (at plan 2) 'guards') }
	for plan plans {
		for step (at (at plan 2) 'steps') {
			name = (at step 2)
			if (contains stepNames name) { error 'SFC: a step variable cannot be owned by two charts' }
			if (contains guardNames name) { error 'SFC: step state cannot also be another chart transition' }
			add stepNames name
		}
	}
	modules = (list (main p))
	for lib (values (getField p 'libraries')) { if (not (lib === reserved)) { add modules lib } }
	allNames = (dictionary)
	for module modules {
		for name (variableNames module) {
			if (contains variables name) { error 'SFC: generated shared variable name collides with user data' }
			atPut allNames name true
		}
		for func (functions module) {
			for plan plans {
				if (beginsWith (functionName func) (at plan 3)) { error 'SFC: generated function namespace collides with user data' }
			}
		}
	}
	for name variables { atPut allNames name true }
	if ((count allNames) > 128) { error 'SFC: shared variable limit exceeded' }
	text = (join 'module ''_SFC workers'' Control' (newline) 'description ''Generated cooperative SFC workers v1''' (newline)
		'variables ' (joinStrings variables ' ') (newline) (joinStrings definitions (newline)))
	lib = (loadFromCmds (newMicroBlocksModule) (parse text))
	atPut (getField p 'libraries') '_SFC workers' lib
	sfcWorkerPlans = plans
	sfcWorkerSource = source
}

to sfcUserSource p reserved {
	source = (codeString (main p) p)
	for lib (values (getField p 'libraries')) {
		if (not (lib === reserved)) { source = (join source (newline) (codeString lib p)) }
	}
	return source
}

method sfcWorkerPlan SmallRuntime cmd {
	sfcPrepareWorkers this
	for plan sfcWorkerPlans { if (cmd === (first plan)) { return plan } }
	error 'SFC: chart does not belong to the saved project scripts'
}

method instructionsForSFCBranches SmallCompiler cmd {
	plan = (sfcWorkerPlan (smallRuntime) cmd)
	graph = (at plan 2)
	for step (at graph 'steps') { sfcSharedVariable this (at step 2) }
	for name (at graph 'guards') { sfcSharedVariable this name }
	invocation = (newReporter (sfcPrivate (at plan 3) 'owner') 0)
	return (instructionsForCmdList this (newCommand 'if' (newReporter 'not' invocation) (newCommand 'return' false)))
}

method sfcPlansForReport SmallRuntime {
	result = (list)
	if (isNil sfcWorkerPlans) { return result }
	for plan sfcWorkerPlans {
		graph = (at plan 2)
		entry = (dictionary)
		steps = (list)
		for step (at graph 'steps') { add steps (array (first step) (at step 2)) }
		atPut entry 'steps' steps
		atPut entry 'initial' (at graph 'initial')
		atPut entry 'edges' (at graph 'edges')
		atPut entry 'guards' (at graph 'guards')
		atPut entry 'prefix' (at plan 3)
		atPut entry 'worker_count' (count steps)
		add result entry
	}
	return result
}

method sfcCancelPlan SmallRuntime chunkID {
	commands = (list)
	if (isNil sfcWorkerPlans) { return commands }
	for key (keys chunkIDs) {
		entry = (at chunkIDs key)
		if (and ((first entry) == chunkID) (isClass key 'Block')) {
			for node (allBlocks (expression key)) {
				for plan sfcWorkerPlans {
					if (node === (first plan)) {
						graph = (at plan 2)
						prefix = (at plan 3)
						// Stop owned worker chunks as well as the coordinator. Do not
						// wait for a potentially suspended user action to return.
						for step (at graph 'steps') {
							id = (lookupChunkID this (sfcPrivate prefix 'worker' (first step)))
							if (notNil id) { add commands (array 'stop' id false) }
						}
						for pair (array (array (sfcPrivate prefix 'run') false) (array (sfcPrivate prefix 'active') 0) (array (sfcPrivate prefix 'status') -3)) {
							id = (at (getField (project scripter) 'varIndices') (first pair))
							if (notNil id) { add commands (array 'set' id (at pair 2)) }
						}
						for step (at graph 'steps') {
							id = (at (getField (project scripter) 'varIndices') (at step 2))
							if (notNil id) { add commands (array 'set' id false) }
						}
					}
				}
			}
		}
	}
	return commands
}

method sfcCancelOwner SmallRuntime chunkID {
	for command (sfcCancelPlan this chunkID) {
		if ((first command) == 'stop') { sendMsg this 'stopChunkMsg' (at command 2) }
		if ((first command) == 'set') { setVar this (at command 2) (at command 3) }
	}
}
