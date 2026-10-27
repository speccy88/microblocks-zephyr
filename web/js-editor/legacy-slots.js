// SPDX-License-Identifier: MPL-2.0
// UNO Q matrix adaptation of the pinned GP UnoQMatrixSlot.gp.
// Original MicroBlocks slot: Copyright 2019 John Maloney, Bernat Romagosa,
// and Jens Mönig. Exact GP source provenance is recorded in dependencies/.
// This local overlay leaves the upstream JS engine unchanged.
(function (root) {
    'use strict';
    const EMPTY = '0'.repeat(104), installed = new WeakMap();
    const patterns = Object.freeze({
        Heart: '00077000770000077770777700077777777777007777777777700077777777700000777777700000007777700000000007000000',
        Smile: ['0000000000000','0007000007000','0007000007000','0000000000000',
            '0070000000700','0007000007000','0000777770000','0000000000000'].join(''),
        Checkerboard: '70707070707070707070707070707070707070707070707070707070707070707070707070707070707070707070707070707070',
        Diagonal: '70000000000000700000000000007000000000000070000000000000700000000000007000000000000070000000000000700000',
        'All on': '7'.repeat(104), Clear: EMPTY
    });
    function valid(pattern) { return typeof pattern === 'string' && pattern.length === 104 && !/[^0-7]/.test(pattern); }
    function preset(name) { return Object.hasOwn(patterns, name) ? patterns[name] : EMPTY; }
    function pixelIndexAt(x, y) {
        if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
        x -= 3; y -= 3;
        if (!Number.isFinite(x) || !Number.isFinite(y) || x < 0 || y < 0 || x >= 130 || y >= 80 || x % 10 >= 8 || y % 10 >= 8) return null;
        return Math.trunc(y / 10) * 13 + Math.trunc(x / 10) + 1;
    }
    function install(Specs, Syntax, Display, Arg, Color, Point, Menu) {
        if (installed.has(Specs)) return installed.get(Specs);
        function UnoQMatrixSlotMorph(pattern) { this.init(pattern); }
        // Existing upstream default/print/copy dispatch recognizes Display.
        // Override its numeric 5x5 representation with the original String ABI.
        UnoQMatrixSlotMorph.prototype = Object.create(Display.prototype);
        UnoQMatrixSlotMorph.prototype.constructor = UnoQMatrixSlotMorph;
        const p = UnoQMatrixSlotMorph.prototype;
        p.init = function (pattern) {
            Arg.prototype.init.call(this);
            this.pixels = EMPTY.split(''); this.lastPaintIndex = null; this.paintValue = '7';
            this.setColor(new Color(30, 45, 70)); this.setContents(pattern); this.fixLayout();
        };
        p.getSpec = () => '%unoqMatrix';
        p.contents = function () { return this.pixels.join(''); };
        p.evaluate = function () { return this.contents(); };
        p.setContents = function (pattern) {
            if (pattern == null || pattern === '') pattern = EMPTY;
            if (!valid(pattern)) return false;
            this.pixels = pattern.split(''); this.mbValue = undefined; this.mbUnsupplied = false;
            this.rerender(); return true;
        };
        p.copyRecordingReferences = function () { const c = this.copy(); c.pixels = this.pixels.slice(); c.lastPaintIndex = null; return c; };
        p.fixLayout = function () { this.bounds.setWidth(152 * this.scale); this.bounds.setHeight(86 * this.scale); };
        p.render = function (ctx) {
            ctx.fillStyle = 'rgb(30,45,70)'; ctx.fillRect(0, 0, this.width(), this.height());
            for (let y = 0; y < 8; y++) for (let x = 0; x < 13; x++) {
                const v = Number(this.pixels[y * 13 + x]);
                ctx.fillStyle = v ? `rgb(${30 + v * 15},${85 + v * 20},${115 + v * 20})` : 'rgb(43,62,88)';
                ctx.fillRect((3 + x * 10) * this.scale, (3 + y * 10) * this.scale, 8 * this.scale, 8 * this.scale);
            }
            ctx.beginPath(); ctx.moveTo(138 * this.scale, 38 * this.scale); ctx.lineTo(148 * this.scale, 38 * this.scale);
            ctx.lineTo(143 * this.scale, 45 * this.scale); ctx.closePath(); ctx.fillStyle = 'rgb(200,215,235)'; ctx.fill();
        };
        p.pixelIndex = function (pos) { const v = pos.subtract(this.topLeft()).divideBy(this.scale); return pixelIndexAt(v.x, v.y); };
        p.paintPixelAt = function (index, value) {
            if (!Number.isInteger(index) || index < 1 || index > 104 || typeof value !== 'string' || value.length !== 1 || !'01234567'.includes(value)) return false;
            this.pixels[index - 1] = value; this.rerender(); this.scriptChanged(); return true;
        };
        p.paintStrokeTo = function (index) {
            if (!Number.isInteger(index) || index < 1 || index > 104) return false;
            if (this.lastPaintIndex == null || this.lastPaintIndex === index) {
                this.lastPaintIndex = index; return this.paintPixelAt(index, this.paintValue);
            }
            const x0 = (this.lastPaintIndex - 1) % 13, y0 = Math.trunc((this.lastPaintIndex - 1) / 13);
            const dx = (index - 1) % 13 - x0, dy = Math.trunc((index - 1) / 13) - y0, steps = Math.max(Math.abs(dx), Math.abs(dy));
            for (let i = 0; i <= steps; i++) this.pixels[Math.round(y0 + dy * i / steps) * 13 + Math.round(x0 + dx * i / steps)] = this.paintValue;
            this.lastPaintIndex = index; this.rerender(); this.scriptChanged(); return true;
        };
        p.mouseDownLeft = function (pos) {
            if (pos.subtract(this.topLeft()).x / this.scale >= 136) { this.userMenu().popUpAtHand(this.world()); return; }
            const i = this.pixelIndex(pos);
            if (i == null) return; // GP ignores an initial press in a cell gap.
            this.lastPaintIndex = null;
            this.paintValue = i && this.pixels[i - 1] !== '0' ? '0' : '7';
            this.mouseMove(pos); this.lockMouseFocus();
        };
        p.mouseMove = function (pos) {
            const i = this.pixelIndex(pos);
            if (i != null) this.paintStrokeTo(i);
            else { const v = pos.subtract(this.topLeft()).divideBy(this.scale); if (v.x < 3 || v.y < 3 || v.x >= 133 || v.y >= 83) this.lastPaintIndex = null; }
        };
        p.userMenu = function () {
            const menu = new Menu(this, 'Matrix images');
            for (const name of Object.keys(patterns)) menu.addItem(name, () => { this.setContents(preset(name)); this.scriptChanged(); });
            return menu;
        };
        const labelPart = Syntax.prototype.labelPart;
        Syntax.prototype.labelPart = function (spec) { return spec === '%unoqMatrix' ? new UnoQMatrixSlotMorph() : labelPart.call(this, spec); };
        const blockForSpec = Specs.blockForSpec;
        Specs.blockForSpec = function (spec, category) {
            return blockForSpec.call(this, Array.isArray(spec) && spec[0] === 'b' ? ['r', ...spec.slice(1)] : spec, category);
        };
        installed.set(Specs, UnoQMatrixSlotMorph); root.UnoQMatrixSlotMorph = UnoQMatrixSlotMorph;
        return UnoQMatrixSlotMorph;
    }
    const api = Object.freeze({valid, preset, pixelIndexAt, install}); root.MicroBlocksLegacySlots = api;
    if (typeof module === 'object' && module.exports) module.exports = api;
})(globalThis);
