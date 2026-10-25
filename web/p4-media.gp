// SPDX-License-Identifier: MPL-2.0
// Real GP block-owned result view. Media never enters the project expression.
defineClass P4MediaView morph block uid kind bitmap expanded userCollapsed state sourceWidth sourceHeight frames rate

to p4MediaKind op {
    if (isOneOf op 'p4TakePicture' '[p4:cameraResult]' '[p4:imageCreate]' '[p4:imageResize]' '[p4:imageGrayscale]' '[p4:imageRGBTensor]') { return 1 }
    if (isOneOf op 'p4RecordPCM' '[p4:audioResult]') { return 2 }
    return 0
}

to p4EnsureMedia b {
    if (notNil (getField b 'p4MediaView')) { return }
    if (isNil (expression b)) { return }
    kind = (p4MediaKind (primName (expression b)))
    if (kind == 0) { return }
    if (isNil (ownerThatIsA (morph b) 'ScriptEditor')) { return }
    next = (global 'p4MediaNextID')
    if (isNil next) { next = 1 }
    if (next > 536870911) { return }
    setGlobal 'p4MediaNextID' (next + 1)
    setField b 'p4MediaID' next
    view = (initialize (new 'P4MediaView') b next kind)
    setField b 'p4MediaView' view
    lineBreak = (labelText b '#BR#')
    add (getField b 'labelParts') (list lineBreak view)
    addPart (morph b) (morph lineBreak)
    addPart (morph b) (morph view)
    layoutChanged b
}

method initialize P4MediaView aBlock anID aKind {
    block = aBlock
    uid = anID
    kind = aKind
    bitmap = nil
    expanded = false
    userCollapsed = false
    state = 'empty'
    sourceWidth = 0
    sourceHeight = 0
    frames = 0
    rate = 16000
    morph = (newMorph this)
    setGrabRule morph 'ignore'
    setTransparentTouch morph true
    p4Size this
    return this
}

method p4Size P4MediaView {
    scale = (blockScale)
    h = (22 * scale)
    if expanded {
        if (and (kind == 1) (notNil bitmap)) { h += ((height bitmap) * scale) }
        if (kind == 2) { h += (30 * scale) }
    }
    setWidth (bounds morph) (160 * scale)
    setHeight (bounds morph) h
}

method drawOn P4MediaView ctx {
    fillRect ctx (gray 244) (left morph) (top morph) (width morph) (height morph)
    if (and expanded (notNil bitmap)) {
        scale = (blockScale)
        x = ((left morph) + (((width morph) - ((width bitmap) * scale)) / 2))
        warpBitmap ctx bitmap x ((top morph) + (22 * scale)) scale scale
    }
}
// Preview pixels and controls are not a request to execute their parent script.
method clicked P4MediaView aHand { return true }
method handDownOn P4MediaView aHand { return true }

to p4MediaBlock uid {
    scripter = (global 'p4MediaScripter')
    if (isNil scripter) { return nil }
    if (isNil (getField scripter 'scriptsFrame')) { return nil }
    for m (allMorphs (morph (scriptEditor scripter)) true) {
        b = (handler m)
        if (and (isClass b 'Block') (uid == (getField b 'p4MediaID'))) { return b }
    }
    return nil
}

to p4MediaTrace compiler expr instructions {
    session = (global 'p4MediaSession')
    if (or (isNil session) (session <= 0)) { return instructions }
    if ((p4MediaKind (primName expr)) == 0) { return instructions }
    scripter = (global 'p4MediaScripter')
    if (isNil scripter) { return instructions }
    for m (allMorphs (morph (scriptEditor scripter)) true) {
        b = (handler m)
        if (and (isClass b 'Block') (=== (expression b) expr)) {
            p4EnsureMedia b
            uid = (getField b 'p4MediaID')
            if (isNil uid) { return instructions }
            addAll instructions (instructionsForExpression compiler uid)
            addAll instructions (instructionsForExpression compiler session)
            add instructions (array 'reporterPrimitive' 'mediaSnapshot' 'p4' 3)
            add instructions (array 'placeholder' 0)
            return instructions
        }
    }
    return instructions
}

to p4MediaLayout scripter {
    out = (dictionary)
    frame = (morph (scriptsFrame scripter))
    atPut out 'clip' (array (left frame) (top frame) (width frame) (height frame))
    views = (list)
    for m (allMorphs (morph (scriptEditor scripter)) true) {
        b = (handler m)
        if (and (isClass b 'Block') ((count views) < 128)) {
            p4EnsureMedia b
            view = (getField b 'p4MediaView')
            if (notNil view) {
                v = (morph view)
                visible = (and ((right v) > (left frame)) ((left v) < (right frame)) ((bottom v) > (top frame)) ((top v) < (bottom frame)))
                if visible { add views (array
                    (getField view 'uid') (getField view 'kind')
                    (left v) (top v) (width v) (height v)
                    (getField view 'expanded') (getField view 'state')
                    (getField view 'sourceWidth') (getField view 'sourceHeight')
                    (getField view 'frames') (getField view 'rate') (primName (expression b))) }
            }
        }
    }
    atPut out 'views' views
    return out
}

to p4MediaStep scripter {
    if (isNil (getField scripter 'scriptsFrame')) { return }
    setGlobal 'p4MediaScripter' scripter
    project = (project scripter)
    if (not (=== project (global 'p4MediaProject'))) {
        setGlobal 'p4MediaProject' project
        notify (api (smallRuntime)) 'p4.media.reset' (array)
    }
    now = (msecsSinceStart)
    last = (global 'p4MediaLastStep')
    if (and (notNil last) ((now - last) < 100)) { return }
    setGlobal 'p4MediaLastStep' now
    layout = (p4MediaLayout scripter)
    signature = (jsonStringify layout)
    if (signature != (global 'p4MediaLastLayout')) {
        setGlobal 'p4MediaLastLayout' signature
        notify (api (smallRuntime)) 'p4.media.layout' layout
    }
}

to p4MediaToggle uid open {
    b = (p4MediaBlock uid)
    if (isNil b) { return false }
    view = (getField b 'p4MediaView')
    if ((getField view 'state') != 'ready') { return false }
    setField view 'expanded' (open == true)
    setField view 'userCollapsed' (not (open == true))
    p4Size view
    layoutChanged b
    return true
}

to p4MediaExpire uid {
    saved = (global 'p4MediaSavedViews')
    if (notNil saved) {
        for i (count saved) {
            entry = (at saved i)
            if (and (notNil entry) ((at entry 1) == uid)) {
                p4MediaClearView (at entry 2)
                atPut saved i nil
            }
        }
    }
    b = (p4MediaBlock uid)
    if (isNil b) { return false }
    view = (getField b 'p4MediaView')
    p4MediaClearView view
    return true
}

to p4MediaClearView view {
    setField view 'bitmap' nil
    setField view 'state' 'expired'
    setField view 'expanded' false
    p4Size view
    b = (getField view 'block')
    if (notNil (ownerThatIsA (morph b) 'ScriptEditor')) { layoutChanged b }
}

// Keep a bounded reference even when a deleted block is in the undo history,
// so cache eviction can clear its bitmap before the block is restored.
to p4MediaRemember uid view {
    saved = (global 'p4MediaSavedViews')
    if (isNil saved) { saved = (newArray 8); setGlobal 'p4MediaSavedViews' saved }
    empty = 0
    for i 8 {
        entry = (at saved i)
        if (and (notNil entry) ((at entry 1) == uid)) { atPut saved i nil }
        if (and (empty == 0) (isNil (at saved i))) { empty = i }
    }
    if (empty == 0) {
        p4MediaClearView (at (at saved 1) 2)
        for i 7 { atPut saved i (at saved (i + 1)) }
        empty = 8
    }
    atPut saved empty (array uid view)
}

to p4MediaResult uid session kind png info {
    if (session != (global 'p4MediaSession')) { return false }
    b = (p4MediaBlock uid)
    if (isNil b) { return false }
    view = (getField b 'p4MediaView')
    if (kind != (getField view 'kind')) { return false }
    if (kind == 1) {
        if ((count png) > 80000) { return false }
        data = (base64Decode png)
        if ((byteCount data) < 24) { return false }
        w = (+ ((byteAt data 17) << 24) ((byteAt data 18) << 16) ((byteAt data 19) << 8) (byteAt data 20))
        h = (+ ((byteAt data 21) << 24) ((byteAt data 22) << 16) ((byteAt data 23) << 8) (byteAt data 24))
        if (or (w < 1) (w > 160) (h < 1) (h > 90)) { return false }
        setField view 'bitmap' (readFrom (new 'PNGReader') data)
        setField view 'sourceWidth' (at info 'source_width')
        setField view 'sourceHeight' (at info 'source_height')
    } else {
        setField view 'frames' (at info 'frames')
        setField view 'rate' (at info 'rate')
    }
    setField view 'state' 'ready'
    setField view 'expanded' (not (true == (getField view 'userCollapsed')))
    p4MediaRemember uid view
    p4Size view
    layoutChanged b
    return true
}
