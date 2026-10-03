/* Real Chrome + Playwright via CDP; persistent profile retained, no file cleanup. */
const { chromium }=require('/Users/lilkoon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {spawn}=require('node:child_process');const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');
(async()=>{
const root=path.resolve(__dirname,'..');const stamp=Date.now();const out=path.join(root,'data','verification',String(stamp));fs.mkdirSync(out,{recursive:true});
const chrome=spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=9224','--user-data-dir='+path.join(out,'chrome-profile')],{stdio:'ignore'});
let browser;try{
  for(let i=0;i<50;i++){try{browser=await chromium.connectOverCDP('http://127.0.0.1:9224');break;}catch{await new Promise(r=>setTimeout(r,200));}}
  assert(browser,'Chrome CDP unavailable');const context=browser.contexts()[0];const page=await context.newPage();await page.setViewportSize({width:1440,height:1000});const errors=[],badRequests=[];
  page.on('pageerror',error=>errors.push(error.message));page.on('response',r=>{if(r.status()>=500)badRequests.push(r.url()+':'+r.status());});
  await page.goto('http://127.0.0.1:8004');await page.locator('#v4-measure-run').waitFor();
  await page.locator('#btn-demo').click();await page.waitForFunction(()=>!!state.session);await page.waitForFunction(()=>!!state.v4Audit);
  const sid=await page.evaluate(()=>state.session.id);
  await page.locator('#v4-units').check();await page.waitForFunction(()=>state.v4Audit?.units_confirmed);
  await page.locator('#v4-ground-run').click();await page.waitForFunction(()=>!!state.v4Ground);
  assert.equal(await page.locator('#v4-ground-mode').inputValue(),'dim');
  for(const mode of ['hide','surface','raw']){await page.locator('#v4-ground-mode').selectOption(mode);await page.waitForTimeout(100);assert.equal(await page.evaluate(()=>state.v4Scene.mode),mode);}
  await page.locator('#objects .object-item').first().click();await page.locator('#v4-scene-focus').check();await page.locator('#v4-measure-run').click();await page.waitForFunction(()=>document.querySelector('#v4-measure-status').textContent.includes('Cảm biến'));
  await page.locator('#v4-raw').click();assert.equal(await page.locator('#v4-scene-focus').isChecked(),false);
  await page.screenshot({path:path.join(out,'desktop-ground.png'),fullPage:true});
  // Exercise real model on an existing local Ultralytics fixture; camera is reference-only.
  await page.locator('#camera-files').setInputFiles(path.resolve(root,'../venv/lib/python3.13/site-packages/ultralytics/assets/bus.jpg'));
  await page.waitForFunction(()=>state.session.cameras.length===1);await page.locator('#v4-image-run').click();
  await page.waitForFunction(()=>/detection ảnh/.test(document.querySelector('#v4-camera-status').textContent),{},{timeout:60000});
  await page.locator('#v4-evidence-run').click();await page.waitForFunction(()=>document.querySelector('#v4-evidence-list').textContent.includes('Ảnh tham khảo'));
  assert((await page.locator('#v4-image-mapping select').count())>0,'Real image model returned no classes on bus fixture');
  await page.screenshot({path:path.join(out,'desktop-camera.png'),fullPage:true});
  await page.reload();await page.locator('#v4-measure-run').waitFor();await page.waitForFunction(()=>!!state.session);assert.equal(await page.evaluate(()=>state.session.id),sid);assert.equal(await page.evaluate(()=>state.session.cameras.length),1);
  const responsive=[];for(const width of [320,768,1024,1440]){await page.setViewportSize({width,height:1000});await page.waitForTimeout(120);const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);responsive.push({width,overflow});await page.screenshot({path:path.join(out,'viewport-'+width+'.png'),fullPage:true});}
  assert.deepEqual(errors,[],'Browser exceptions');assert.deepEqual(badRequests,[],'Server failures');
  const report={session_id:sid,errors,badRequests,responsive,checks:['demo','units confirmation','ground dim/hide/surface/raw','box selection','3D focus','measurement','real YOLO image inference','reference-only evidence','reload'],output:out};
  fs.writeFileSync(path.join(out,'browser-report.json'),JSON.stringify(report,null,2),{flag:'wx'});console.log(JSON.stringify(report,null,2));
}finally{if(browser)await browser.close();chrome.kill();}
})().catch(error=>{console.error(error);process.exitCode=1;});
