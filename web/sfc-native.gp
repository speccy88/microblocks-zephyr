// SPDX-License-Identifier: MPL-2.0
// Opt-in genuine SmallCompiler adapter. No new VM opcode or primitive.

method sfcSharedVariable SmallCompiler name {
	if (and (isClass name 'Reporter') ('v' == (primName name))) { name = (first (argList name)) }
	if (not (isClass name 'String')) { error 'SFC: select a shared variable' }
	if (or (contains localVars name) (contains argNames name)) {
		error 'SFC: local variables and function parameters cannot be step/transition variables'
	}
	if (not (contains (allVariableNames (project (scripter (smallRuntime)))) name)) {
		error 'SFC: create the shared step/transition variable first'
	}
	return name
}

method instructionsForSFCSequence SmallCompiler args cmd {
	if (sfcHasBranches cmd) { return (instructionsForSFCBranches this cmd) }
	if ((count args) != 1) { error 'SFC: sequence needs one command section' }
	pairs = (list)
	stepNames = (list)
	transitionNames = (list)
	step = (first args)
	while (notNil step) {
		if ('sfcStep' != (primName step)) { error 'SFC: only step/transition pairs belong in a sequence' }
		sa = (argList step)
		if ((count sa) != 3) { error 'SFC: step needs a variable, entry and loop sections' }
		name = (sfcSharedVariable this (first sa))
		if (contains stepNames name) { error 'SFC: a step variable is used twice' }
		add stepNames name
		transition = (nextBlock step)
		if (isNil transition) { error 'SFC: every step needs a following transition' }
		if ('sfcTransition' != (primName transition)) { error 'SFC: ordinary blocks belong inside step entry/loop sections' }
		ta = (argList transition)
		if ((count ta) != 1) { error 'SFC: transition needs one shared variable' }
		guard = (sfcSharedVariable this (first ta))
		add transitionNames guard
		add pairs (array sa guard)
		step = (nextBlock transition)
	}
	if (isEmpty pairs) { error 'SFC: sequence needs a step/transition pair' }
	for name stepNames {
		if (contains transitionNames name) { error 'SFC: step and transition variables must be different' }
	}
	result = (list)
	for name stepNames {
		add result (array 'pushImmediate' falseObj)
		add result (setVar this name)
	}
	for pair pairs {
		sa = (first pair)
		name = (first sa)
		guard = (at pair 2)
		add result (array 'pushImmediate' trueObj)
		add result (setVar this name)
		addAll result (instructionsForCmdList this (at sa 2))
		// A synthetic wrapper owns the yield; the saved action AST is untouched.
		body = (newCommand 'if' true (at sa 3))
		setField body 'nextBlock' (newCommand 'waitMillis' 1)
		condition = (newReporter '==' (newReporter 'v' guard) true)
		if (isNil (at sa 3)) {
			addAll result (instructionsForWaitUntil this (array condition))
		} else {
			addAll result (instructionsForRepeatUntil this (array condition body))
		}
		add result (array 'pushImmediate' falseObj)
		add result (setVar this name)
	}
	return result
}
