// SPDX-License-Identifier: MPL-2.0
// Bounded local startup for small board HTTP servers; no service worker/CDN.
(() => {
    'use strict';
    const config = JSON.parse(document.getElementById('mobile-load-config').textContent);
    const originalFetch = window.fetch.bind(window), queue = [];
    let active = 0;
    const pump = () => {
        while (active < 2 && queue.length) {
            const work = queue.shift(); active++;
            (async () => {
                for (let attempt = 0; ; attempt++) {
                    try {
                        const response = await originalFetch(work.input, work.options);
                        if (![429, 503].includes(response.status) || attempt >= 2) return response;
                        await response.body?.cancel();
                    } catch (error) { if (attempt >= 2 || work.options?.signal?.aborted) throw error; }
                    await new Promise(resolve => setTimeout(resolve, 150 * (attempt + 1)));
                }
            })().then(work.resolve, work.reject).finally(() => { active--; pump(); });
        }
    };
    window.fetch = (input, options) => {
        const url = new URL(typeof input === 'string' || input instanceof URL ? input : input.url, location.href);
        const method = options?.method || input.method || 'GET';
        if (url.origin !== location.origin || !['GET', 'HEAD'].includes(method.toUpperCase())) return originalFetch(input, options);
        if (queue.length >= 128) return Promise.reject(new Error('Local asset request queue exceeded. Reload to retry.'));
        return new Promise((resolve, reject) => { queue.push({input, options, resolve, reject}); pump(); });
    };
    async function resource(tag, attribute, url) {
        if (new URL(url, location.href).origin !== location.origin) throw new Error('Non-local startup resource');
        for (let attempt = 0; ; attempt++) {
            const node = document.createElement(tag);
            if (tag === 'link') node.rel = 'stylesheet';
            try {
                await new Promise((resolve, reject) => {
                    const timer = setTimeout(() => reject(new Error('Asset deadline: ' + url)), 30000);
                    node.onload = () => { clearTimeout(timer); resolve(); };
                    node.onerror = () => { clearTimeout(timer); reject(new Error('Cannot load local asset: ' + url)); };
                    node[attribute] = url; document.head.append(node);
                });
                return;
            } catch (error) {
                node.remove(); if (attempt >= 2) throw error;
                await new Promise(resolve => setTimeout(resolve, 150 * (attempt + 1)));
            }
        }
    }
    async function start() {
        try {
            for (const link of document.querySelectorAll('link[data-mobile-href]')) await resource('link', 'href', link.dataset.mobileHref);
            for (const image of document.querySelectorAll('img[data-mobile-src]')) {
                await new Promise(resolve => { image.onload = image.onerror = resolve; image.src = image.dataset.mobileSrc; });
            }
            for (const script of config.scripts) {
                if (script.src) await resource('script', 'src', script.src);
                else { const node = document.createElement('script'); node.textContent = script.inline; document.head.append(node); }
            }
            window.dispatchEvent(new Event(config.profile.startupEvent));
            window.microblocksMobileStart();
            setTimeout(() => MB_editor.reportWaitingError(), 750);
            document.documentElement.dataset.mobileAssets = 'loaded';
        } catch (error) {
            document.documentElement.dataset.mobileAssets = 'failed';
            const message = document.querySelector('.app-preloader__text');
            if (message) message.textContent = error.message + '. Reload to retry.';
            console.error(error);
        }
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
    else start();
})();
