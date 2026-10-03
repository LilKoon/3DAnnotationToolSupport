/* Real Chrome + Playwright via CDP; persistent profile retained, no file cleanup. */
const { chromium }=require('/Users/lilkoon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const {spawn}=require('node:child_process');const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');
(async()=>{
const root=path.resolve(__dirname,'..');const stamp=Date.now();const out=path.join(root,'data','verification',String(stamp));fs.mkdirSync(out,{recursive:true});
const chrome=spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=9224','--user-data-dir='+path.join(out,'chrome-profile')],{stdio:'ignore'});
let browser;try{
  for(let i=0;i<50;i++){try{browser=await chromium.connectOverCDP('http://127.0.0.1:9224');break;}catch{await new Promise(r=>setTimeout(r,200));}}
  assert(browser,'Chrome CDP unavailable');const context=browser.contexts()[0];const page=await context.newPage();await page.setViewportSize({width:1440,height:1000});const errors=[],badRequests=[],consoleErrors=[];
  page.on('console',message=>{if(message.type()==='error')consoleErrors.push(message.text());});
  page.on('pageerror',error=>errors.push(error.message));page.on('response',r=>{if(r.status()>=500)badRequests.push(r.url()+':'+r.status());});
  await page.goto('http://127.0.0.1:8004');await page.locator('#v4-auto-ground').waitFor();await page.locator('#v4-z-min').waitFor();await page.locator('#v4-measure-run').waitFor();
  await page.locator('#btn-demo').click();await page.waitForFunction(()=>!!state.session);await page.waitForFunction(()=>!!state.v4Audit);
  let sid=await page.evaluate(()=>state.session.id);
  await page.locator('#v4-units').check();await page.waitForFunction(()=>state.v4Audit?.units_confirmed);
  await page.locator('#v4-ground-run').click();await page.waitForFunction(()=>!!state.v4Ground);
  assert.equal(await page.locator('#v4-ground-mode').inputValue(),'dim');
  for(const mode of ['hide','surface','raw']){await page.locator('#v4-ground-mode').selectOption(mode);await page.waitForTimeout(100);assert.equal(await page.evaluate(()=>state.v4Scene.mode),mode);}
  await page.locator('#objects .object-item').first().click();await page.locator('#v4-scene-focus').check();await page.locator('#v4-measure-run').click();await page.waitForFunction(()=>document.querySelector('#v4-measure-status').textContent.includes('Cảm biến'));
  await page.locator('#v4-raw').click();assert.equal(await page.locator('#v4-scene-focus').isChecked(),false);
  await page.locator('#v4-ground-mode').selectOption('surface');await page.waitForTimeout(100);await page.screenshot({path:path.join(out,'desktop-ground.png'),fullPage:true});
  // Exercise real model on an existing local Ultralytics fixture; camera is reference-only.
  await page.locator('#camera-files').setInputFiles(path.resolve(root,'../venv/lib/python3.13/site-packages/ultralytics/assets/bus.jpg'));
  await page.waitForFunction(()=>state.session.cameras.length===1);await page.waitForFunction(()=>document.querySelector('#v4-camera-index').options.length===1);await page.locator('#v4-image-run').click();
  await page.waitForFunction(()=>/detection ảnh/.test(document.querySelector('#v4-camera-status').textContent),{},{timeout:60000});
  await page.locator('#v4-evidence-run').click();await page.waitForFunction(()=>document.querySelector('#v4-evidence-list').textContent.includes('Ảnh tham khảo'));
  assert((await page.locator('#v4-image-mapping select').count())>0,'Real image model returned no classes on bus fixture');
  await page.screenshot({path:path.join(out,'desktop-camera.png'),fullPage:true});
  await page.reload();await page.locator('#v4-measure-run').waitFor();await page.waitForFunction(()=>!!state.session);assert.equal(await page.evaluate(()=>state.session.id),sid);assert.equal(await page.evaluate(()=>state.session.cameras.length),1);

  // Calibration form test: synthetic matrix is deliberately unreviewed and unsynchronized.
  const imageDimensions=await page.locator('[data-v4-camera="0"] img').evaluate(img=>({width:img.naturalWidth,height:img.naturalHeight}));
  const calibration={K:[[500,0,imageDimensions.width/2],[0,500,imageDimensions.height/2],[0,0,1]],T_camera_from_lidar:[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]],...imageDimensions};
  await page.getByText('Hiệu chuẩn & đồng bộ',{exact:true}).click();
  await page.locator('#v4-calibration-json').fill(JSON.stringify(calibration));
  await page.locator('#v4-calibration-save').click();await page.waitForFunction(()=>document.querySelector('#v4-camera-status').textContent.includes('Đã lưu calibration'));
  assert.equal(await page.locator('#v4-calibration-reviewed').isChecked(),false);
  await page.locator('#v4-evidence-run').click();await page.waitForFunction(()=>document.querySelector('#v4-evidence-list').textContent.includes('Ảnh tham khảo'));
  await page.locator('#v4-quality-run').click();await page.waitForFunction(()=>document.querySelector('#v4-quality-status').textContent.includes('cặp overlap'));
  // Auto-ground on a fresh frame, then a real ~299k-point sensor cloud.
  await page.locator('#v4-auto-ground').check();await page.locator('#btn-demo').click();
  await page.waitForFunction(old=>state.session?.id!==old&&!!state.v4Ground,sid);sid=await page.evaluate(()=>state.session.id);
  await page.locator('#file').setInputFiles(path.resolve(root,'../v3/data/sessions/018f40c666d24cc8be4734ab98e02d8d.bin'));
  await page.waitForFunction(old=>state.session?.id!==old&&!!state.v4Ground,sid);sid=await page.evaluate(()=>state.session.id);
  await page.locator('#v4-auto-ground').uncheck();
  await page.locator('#v4-ground-mode').selectOption('surface');
  await page.locator('#v4-z-min').fill('-2');await page.locator('#v4-z-min').press('Tab');
  await page.locator('#v4-z-max').fill('3');await page.locator('#v4-z-max').press('Tab');
  const redraw=await page.evaluate(()=>{const values=[];for(let i=0;i<20;i++){const start=performance.now();renderOne('main');values.push(performance.now()-start);}values.sort((a,b)=>a-b);return {points:state.points.length,p50_ms:values[10],p95_ms:values[19]};});
  await page.screenshot({path:path.join(out,'real-cloud-surface.png'),fullPage:true});
  await page.locator('#v4-raw').click();assert.equal(await page.locator('#v4-z-min').inputValue(),'');

  const responsive=[];for(const width of [320,768,1024,1440]){await page.setViewportSize({width,height:1000});await page.waitForTimeout(120);const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);responsive.push({width,overflow});await page.screenshot({path:path.join(out,'viewport-'+width+'.png'),fullPage:true});}
  assert.deepEqual(consoleErrors,[],'Console errors');assert(responsive.every(r=>!r.overflow),'Responsive overflow');assert.deepEqual(errors,[],'Browser exceptions');assert.deepEqual(badRequests,[],'Server failures');
  const report={session_id:sid,errors,consoleErrors,badRequests,responsive,redraw,checks:['demo','units confirmation','ground dim/hide/surface/raw','box selection','3D focus','measurement','real YOLO image inference','reference-only evidence','reload','unreviewed calibration import','quality diagnostics','automatic per-frame ground','real point-cloud upload','height filters','render timing'],output:out};
  fs.writeFileSync(path.join(out,'browser-report.json'),JSON.stringify(report,null,2),{flag:'wx'});console.log(JSON.stringify(report,null,2));
}finally{if(browser)await browser.close();chrome.kill();}
})().catch(error=>{console.error(error);process.exitCode=1;});
