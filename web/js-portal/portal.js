// SPDX-License-Identifier: MPL-2.0
// The launcher owns no project or connection; native links open separate tabs.
(() => {
    'use strict';
    const requested = new URLSearchParams(location.search).get('board');
    for (const choice of document.querySelectorAll('.board-choice')) {
        if (choice.dataset.board === requested) choice.setAttribute('aria-current', 'true');
    }
})();
