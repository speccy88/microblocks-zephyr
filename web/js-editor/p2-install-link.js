// SPDX-License-Identifier: MPL-2.0
// Installation is a separate, explicit action and owns no editor connection.
if (typeof MicroBlocksJSProfile==='object' && MicroBlocksJSProfile.id==='propeller2') {
    window.addEventListener('DOMContentLoaded',()=>{
        if(document.getElementById('p2-install-vm'))return;
        const link=document.createElement('a');link.id='p2-install-vm';link.textContent='Install P2 SmallVM';
        link.href='../../install/propeller2/index.html';link.target='_blank';link.rel='noopener';
        link.style.cssText='margin-left:10px;color:#075b82';
        const panel=document.querySelector('body > div[role="status"]');
        (panel||document.body).append(link);
    });
}
