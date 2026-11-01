// SPDX-License-Identifier: MPL-2.0
// Ephemeral, bounded, read-only live state for genuine MicroBlocks step blocks.

to sfcSetBlockActive b flag {
	flag = (flag == true)
	if ((true == (getField b 'sfcLiveActive')) == flag) { return }
	setField b 'sfcLiveActive' flag
	setField b 'pathCache' nil
	if (notNil (morph b)) { rerender (morph b) }
}

to sfcBlockDisplayColor b {
	if (true == (getField b 'sfcLiveActive')) { return (color 34 190 68) }
	return (getField b 'color')
}

to sfcLiveClear runtime {
	state = (global 'sfcLiveState')
	if (isNil state) { return }
	for record (at state 'records') { sfcSetBlockActive (first record) false }
	setGlobal 'sfcLiveState' nil
}

to sfcLiveState runtime {
	state = (global 'sfcLiveState')
	if (and (notNil state) (runtime === (at state 'runtime'))) { return state }
	sfcLiveClear runtime
	state = (dictionary)
	atPut state 'runtime' runtime
	atPut state 'records' (array)
	atPut state 'pending' (dictionary)
	atPut state 'values' (dictionary)
	atPut state 'stopped' (dictionary)
	atPut state 'cursor' 0
	atPut state 'lastPoll' -1000
	setGlobal 'sfcLiveState' state
	return state
}

to sfcLiveBind runtime records now {
	state = (sfcLiveState runtime)
	for old (at state 'records') {
		found = false
		for record records { if ((first record) === (first old)) { found = true } }
		if (not found) { sfcSetBlockActive (first old) false }
	}
	atPut state 'records' records
	sfcLiveExpire runtime now
}

to sfcLiveRunning runtime chunkID {
	state = (global 'sfcLiveState')
	if (notNil state) {
		if (contains (at state 'stopped') chunkID) { return false }
	}
	flags = (getField runtime 'chunkRunning')
	if (or (isNil flags) (isNil chunkID)) { return false }
	return (true == (at flags (chunkID + 1)))
}

to sfcLiveExpire runtime now {
	state = (sfcLiveState runtime)
	for record (at state 'records') {
		value = (at (at state 'values') (at record 2))
		active = false
		if (and (notNil value) (sfcLiveRunning runtime (at record 3))) {
			active = (and (true == (first value)) ((now - (at value 2)) <= 1500))
		}
		sfcSetBlockActive (first record) active
	}
}

to sfcLiveRequests runtime now {
	state = (sfcLiveState runtime)
	requests = (list)
	if ((now - (at state 'lastPoll')) < 250) { return requests }
	atPut state 'lastPoll' now
	records = (at state 'records')
	if (isEmpty records) { return requests }
	// At most four asynchronous read requests per 250 ms; no writes or retries.
	repeat (count records) {
		cursor = (((at state 'cursor') % (count records)) + 1)
		atPut state 'cursor' cursor
		record = (at records cursor)
		id = (at record 2)
		pending = (at (at state 'pending') id)
		if (and (sfcLiveRunning runtime (at record 3)) (or (isNil pending) ((now - pending) > 1500))) {
			atPut (at state 'pending') id now
			add requests id
		}
		if ((count requests) >= 4) { return requests }
	}
	return requests
}

to sfcLiveReceive runtime id value now {
	state = (global 'sfcLiveState')
	if (or (isNil state) (not (runtime === (at state 'runtime')))) { return false }
	pending = (at state 'pending')
	if (not (contains pending id)) { return false }
	remove pending id
	atPut (at state 'values') id (array (true == value) now)
	sfcLiveExpire runtime now
	return true
}

to sfcLiveChunkStopped runtime chunkID {
	state = (global 'sfcLiveState')
	if (isNil state) { return }
	atPut (at state 'stopped') chunkID true
	for record (at state 'records') {
		if ((at record 3) == chunkID) {
			remove (at state 'pending') (at record 2)
			remove (at state 'values') (at record 2)
			sfcSetBlockActive (first record) false
		}
	}
}

to sfcLiveChunkStarted runtime chunkID {
	state = (global 'sfcLiveState')
	if (notNil state) { remove (at state 'stopped') chunkID }
}

to sfcLivePoll runtime {
	s = (scripter runtime)
	if (or (not (serialPortOpen runtime)) (isNil (getField s 'scriptsFrame'))) {
		sfcLiveClear runtime
		return
	}
	state = (sfcLiveState runtime)
	project = (project s)
	if (not ((at state 'project') === project)) {
		sfcLiveClear runtime
		state = (sfcLiveState runtime)
		atPut state 'project' project
	}
	records = (list)
	for m (allMorphs (morph (scriptEditor s)) true) {
		b = (handler m)
		if (isClass b 'Block') {
			expr = (expression b)
			if (and (notNil expr) ('sfcStep' == (primName expr))) {
				id = (at (getField project 'varIndices') (first (argList expr)))
				chunkID = (lookupChunkID runtime (topBlock b))
				if (and (notNil id) (notNil chunkID)) { add records (array b id chunkID) }
			}
		}
	}
	now = (msecsSinceStart)
	sfcLiveBind runtime records now
	for id (sfcLiveRequests runtime now) { getVar runtime id }
}
