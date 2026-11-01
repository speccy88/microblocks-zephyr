// SPDX-License-Identifier: MIT
// Compare the port with the verified GP virtual source, not copied expectations.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const crypto = require('node:crypto');
const path = require('node:path');
const root = path.resolve(__dirname, '../../..');
const model = require(path.join(root, 'web/js-editor/legacy-slots.js'));
const pin = JSON.parse(fs.readFileSync(path.join(root, 'dependencies/unoq-matrix-gp.json')));
const raw = fs.readFileSync(process.argv[2]);
const hash = b => crypto.createHash('sha256').update(b).digest('hex');
assert.equal(hash(raw), pin.source_sha256);
const gp = raw.toString('utf8');
const presets = {};
for (const name of ['Heart', 'Smile', 'Checkerboard', 'Diagonal', 'All on', 'Clear']) {
    let expected;
    if (name === 'Clear') {
        assert.match(gp, /return \(joinStringArray \(newArray 104 '0'\)\)/);
        expected = '0'.repeat(104);
    } else {
        const body = gp.match(new RegExp("\\(name == '" + name + "'\\) \\{([\\s\\S]*?)\\n\\t\\}"))[1];
        const digits = [...body.matchAll(/'([0-7]+)'/g)].map(m => m[1]);
        expected = name === 'All on' ? digits[0].repeat(104) : digits.join('');
    }
    assert.equal(expected.length, 104);
    assert.equal(model.preset(name), expected, name);
    presets[name] = hash(Buffer.from(expected));
}
console.log(JSON.stringify({source_gp_sha256: hash(raw), presets_compared: 6, presets,
    hardware: false, local_adapter_sha256: hash(fs.readFileSync(path.join(root, 'web/js-editor/legacy-slots.js')))}, null, 2));
