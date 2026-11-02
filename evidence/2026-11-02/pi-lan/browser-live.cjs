// SPDX-License-Identifier: MIT
// Real LAN HTTP, real WebSocket, actual compiler and physical Pi SmallVM.
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
async function bounded(work,label,ms=20000){let timer;try{return await Promise.race([work,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Deadline: '+label)),ms);})]);}finally{clearTimeout(timer);}}
(async()=>{
    const browser=await chromium.launch({executablePath:process.env.EDGE_EXE,headless:true});
    const result={url:'http://192.168.1.105:8877/',physical_pi:true,physical_iphone:false,
        browser_engine:'Chromium/Edge',viewport:'390x844',socket_mocked:false,authentication:false,encryption:false};
    let page;
    try {
        const context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,acceptDownloads:true});
        const errors=[],failed=[];
        await context.addInitScript(()=>{
            const Actual=window.WebSocket;window.actualSockets=[];
            window.WebSocket=class extends Actual {constructor(...args){super(...args);actualSockets.push(this);}};
        });
        page=await context.newPage();page.setDefaultTimeout(30000);page.on('pageerror',e=>errors.push(e.message));
        page.on('console',m=>{if(m.type()==='error')console.log('browser error:',m.text());});
        page.on('requestfailed',r=>failed.push({url:r.url(),reason:r.failure()?.errorText}));
        await page.goto(result.url);
        console.log('LAN document loaded');
        await page.waitForFunction(()=>document.documentElement.dataset.mobileAssets==='loaded');
        console.log('Mobile assets loaded');
        await page.waitForFunction(()=>typeof world!=='undefined'&&world&&MicroBlocksIPhone.gestures);
        console.log('Mobile workspace ready');
        await page.locator('[data-ide="app-preloader"]').waitFor({state:'hidden'});
        assert(await page.evaluate(()=>MicroBlocksBrowser.available));
        assert.equal(await page.locator('#pi-session-key').count(),0);
        await page.locator('#iphone-connect').click();
        assert.equal(await page.locator('#iphone-address').inputValue(),'192.168.1.105');
        await page.locator('#iphone-open').click();
        console.log('Connect requested');
        await page.waitForFunction(()=>MB_connection.connectedToBoard()&&MB_connection.vmVersion===417);
        await page.waitForFunction(()=>!document.querySelector('.iphone-connect-sheet').open);
        result.vm_version=await page.evaluate(()=>MB_connection.vmVersion);
        result.board=await page.evaluate(()=>MB_connection.boardType);
        console.log('Real VM connected',result.vm_version,result.board);
        await page.evaluate(()=>{window.actualResults=[];const show=MB_editor.showResult.bind(MB_editor);
            MB_editor.showResult=(id,value)=>{actualResults.push(value);show(id,value);};});
        result.arithmetic=[];
        for(const [a,b,expected] of [[5,7,12],[6,7,13]]){
            await bounded(page.evaluate(async({a,b})=>{
                if(!window.actualBlock){
                    MB_editor.unsavedEdits=false;
                    await MB_editor.openProjectFromString(`projectName 'Pi LAN'\nmodule 'main'\nscript 40 60 (+ ${a} ${b})\n`,'Pi LAN.ubp');
                    window.actualBlock=MB_editor.scripts.children.find(x=>x instanceof ReporterBlockMorph);
                } else {actualBlock.inputs()[0].setContents(a);actualBlock.scriptChanged();actualBlock.changed();}
                if(!actualBlock||!await MB_editor.saveBeforeRun())throw Error('Real compiler upload failed');
                window.actualChunk=MB_editor.codeManager.lookupChunkID(actualBlock);
                window.actualCRC=MB_editor.codeManager.chunkEntryForBlock(actualBlock)[1];
                if(actualChunk==null||!actualCRC)throw Error('Real upload CRC unavailable');
            },{a,b}),'real compiler/upload');
            console.log('Program uploaded',expected);
            const count=await page.evaluate(()=>actualResults.length);
            await page.evaluate(()=>MB_editor.codeManager.evalOnBoard(actualBlock));
            await page.waitForFunction(({count,expected})=>actualResults.slice(count).includes(expected),{count,expected},{timeout:15000});
            result.arithmetic.push(expected);
            console.log('VM result',expected);
        }
        result.crc_upload=true;result.live_edit=true;
        await page.screenshot({path:path.join(__dirname,'live-pi-programming.png')});
        await page.locator('#iphone-menu').click();
        const pendingDownload=page.waitForEvent('download',{timeout:10000});
        await page.locator('#iphone-save').click();
        const download=await pendingDownload;
        const savedPath=path.join(__dirname,'Pi-LAN-test.ubp');await download.saveAs(savedPath);
        const saved=fs.readFileSync(savedPath,'utf8');assert(await page.evaluate(text=>MB_Project.isProjectText(text),saved));
        result.project_export=true;
        const importing=bounded(page.evaluate(async contents=>{
            await MB_editor.openProjectFromString(contents,'Pi-LAN-test.ubp');
            window.actualBlock=MB_editor.scripts.children.find(x=>x instanceof ReporterBlockMorph);
            if(!actualBlock||!await MB_editor.saveBeforeRun())throw Error('Saved project import/upload failed');
            window.actualChunk=MB_editor.codeManager.lookupChunkID(actualBlock);
            window.actualCRC=MB_editor.codeManager.chunkEntryForBlock(actualBlock)[1];
        },saved),'saved project import');
        await page.getByText('Yes',{exact:true}).click();
        await importing;
        if(await page.locator('#iphone-menu').getAttribute('aria-expanded')==='true')await page.locator('#iphone-menu').click();
        result.project_import=true;
        await page.evaluate(async()=>{await MB_connection.sendMsg('stopAllMsg');await MB_connection.sendQueue;MB_connection.disconnect();});
        await page.waitForFunction(()=>!MB_connection.connectedToBoard());
        await page.locator('#iphone-connect').click();await page.locator('#iphone-open').click();
        await page.waitForFunction(()=>MB_connection.connectedToBoard()&&MB_connection.vmVersion===417);
        await page.waitForFunction(()=>!document.querySelector('.iphone-connect-sheet').open);
        await page.evaluate(()=>{MB_editor.codeManager.lastCRC=null;MB_connection.sendMsg('getChunkCRCMsg',actualChunk);});
        await page.waitForFunction(()=>MB_editor.codeManager.lastCRC!==null);
        assert(await page.evaluate(()=>JSON.stringify(Array.from(MB_editor.codeManager.lastCRC))===JSON.stringify(Array.from(actualCRC))));
        result.stop_reconnect=true;result.crc_readback_after_reconnect=true;
        const count=await page.evaluate(()=>actualResults.length);
        await page.evaluate(()=>MB_editor.codeManager.evalOnBoard(actualBlock));
        await page.waitForFunction(count=>actualResults.slice(count).includes(13),count);
        result.reexecuted_after_reconnect=13;
        await page.evaluate(()=>MB_connection.disconnect());
        assert.deepEqual(errors,[]);assert.deepEqual(failed,[]);
        result.page_errors=errors;result.failed_requests=failed;result.result='PASS';
        fs.writeFileSync(path.join(__dirname,'live-pi-programming.json'),JSON.stringify(result,null,2)+'\n');
        console.log(JSON.stringify(result));
    } catch(error){
        result.result='FAIL';result.error=error.message;
        if(page){result.diagnostic=await bounded(page.evaluate(()=>({assets:document.documentElement.dataset.mobileAssets,
            available:window.MicroBlocksBrowser?.available,status:document.querySelector('#iphone-status')?.textContent,
            vm:typeof MB_connection!=='undefined'?MB_connection.vmVersion:null,results:window.actualResults})),'diagnostic',5000).catch(()=>null);
            await page.screenshot({path:path.join(__dirname,'live-pi-failure.png'),timeout:5000}).catch(()=>{});}
        fs.writeFileSync(path.join(__dirname,'live-pi-programming.json'),JSON.stringify(result,null,2)+'\n');
        throw error;
    } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
