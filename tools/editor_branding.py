"""Main-owned plain wordmark; keep upstream engine and image bytes intact."""
# SPDX-License-Identifier: MPL-2.0
import re


def plain_wordmark(html):
    for filename, markup in [
        ('microblocks-ide-logo.svg', '<span class="editor-wordmark" style="display:block;color:#ecedf1;font:700 20px/36px system-ui,sans-serif">MicroBlocks</span>'),
        ('logo-preloader.svg', '<span class="preloader-wordmark" style="font:700 28px system-ui,sans-serif">MicroBlocks</span>'),
    ]:
        html, count = re.subn(r'<img\b(?=[^>]*\bsrc="img/' + re.escape(filename) + r'")[^>]*>', lambda _: markup, html)
        if count != 1:
            raise ValueError('Review changed editor branding anchor: ' + filename)
    return html
