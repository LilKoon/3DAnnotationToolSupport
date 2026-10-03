/* V4 additions keep the V3 editor, labels and publish flow intact. */
(function(){
  const panel=document.createElement('section');panel.className='card v4-card';panel.innerHTML=`<h2>Mặt đất & dữ liệu</h2><p>Giữ nguyên LiDAR gốc. Vùng chưa chắc chắn vẫn hiển thị.</p><label><input type="checkbox" id="v4-units"> Tôi xác nhận dữ liệu là mét, X trước / Y trái / Z lên</label><button id="v4-ground-run">Quét mặt đất</button><p id="v4-audit" class="v4-status" role="status">Mở một frame để kiểm tra dữ liệu.</p><p id="v4-ground-status" class="v4-status" role="status"></p><p id="v4-contact" role="status">Chọn box để xem độ cao so với mặt đất.</p>`;
  document.querySelector('.left-panel').prepend(panel);
  const toolbar=document.createElement('div');toolbar.className='v4-toolbar';toolbar.innerHTML=`<label>Mặt đất <select id="v4-ground-mode"><option value="raw">Điểm gốc</option><option value="dim">Mờ</option><option value="hide">Ẩn ground</option><option value="surface">Bề mặt liền</option></select></label><label><input id="v4-scene-focus" type="checkbox"> Focus box 3D</label><label>Phạm vi XY <input id="v4-range" type="number" value="100" min="1" max="500" step="5" aria-label="Phạm vi XY theo đơn vị dữ liệu" style="width:64px"></label><button id="v4-raw">Xem điểm gốc</button>`;
  document.querySelector('.workspace').insertBefore(toolbar,$('view-3d'));
  state.v4Scene={...V4Scene.defaults};let epoch=0;
  function status(id,text){$(id).textContent=text;}
  async function sessionChanged(data){
    const token=++epoch;state.v4Ground=null;state.v4Audit=null;state.v4Scene.mode='raw';$('v4-ground-mode').value='raw';$('v4-units').checked=false;status('v4-ground-status','');
    status('v4-audit','Đang kiểm tra…');
    try{const report=await api(`/api/v4/sessions/${data.id}/audit`);if(token!==epoch)return;state.v4Audit=report;$('v4-units').checked=report.units_confirmed;status('v4-audit',`${report.point_count.toLocaleString()} điểm gốc · ${report.camera_count} camera\n${report.warnings.join('\n')||'Đơn vị và dữ liệu camera đã được xác nhận.'}`);}catch(error){if(token===epoch)status('v4-audit',error.message);}
    selectionChanged();if(globalThis.V4Camera)V4Camera.sessionChanged(data);
  }
  async function scan(){
    if(!state.session)return;const id=state.session.id,token=epoch;$('v4-ground-run').disabled=true;status('v4-ground-status','Đang quét mặt đất…');const start=performance.now();
    try{const result=await api(`/api/v4/sessions/${id}/ground`,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});if(token!==epoch)return;
      state.v4Ground=result;state.v4Scene.mode='dim';$('v4-ground-mode').value='dim';status('v4-ground-status',`${result.counts.ground.toLocaleString()} ground · ${result.counts.unknown.toLocaleString()} chưa chắc\n${Math.round(performance.now()-start)} ms · ${result.surface.length} tam giác`);render();selectionChanged();
    }catch(error){if(token===epoch)status('v4-ground-status',error.message);}finally{$('v4-ground-run').disabled=false;}
  }
  let selectionEpoch=0;
  async function selectionChanged(){
    const box=selected(),token=++selectionEpoch;
    if(!box||!state.v4Ground){status('v4-contact','Quét ground và chọn box để xem độ cao đáy.');return;}
    const id=state.session.id;
    try{const result=await api(`/api/v4/sessions/${id}/ground-contact/${encodeURIComponent(box.id)}`);if(token!==selectionEpoch||state.session?.id!==id)return;status('v4-contact',result.available?`Đáy box so với ground: ${result.clearance_m.toFixed(2)} ${result.units_confirmed?'m':'đơn vị dữ liệu'} · chỉ tham khảo`:result.reason);}catch(error){if(token===selectionEpoch)status('v4-contact',error.message);}
    if(globalThis.V4Camera)V4Camera.selectionChanged();
  }
  $('v4-ground-run').onclick=scan;
  $('v4-ground-mode').onchange=()=>{if($('v4-ground-mode').value!=='raw'&&!state.v4Ground){$('v4-ground-mode').value='raw';status('v4-ground-status','Quét mặt đất trước khi chọn chế độ.');return;}state.v4Scene.mode=$('v4-ground-mode').value;render();};
  $('v4-raw').onclick=()=>{state.v4Scene={...V4Scene.defaults};$('v4-ground-mode').value='raw';$('v4-scene-focus').checked=false;$('v4-range').value=100;render();};
  $('v4-scene-focus').onchange=()=>{state.v4Scene.focus=$('v4-scene-focus').checked;render();};
  $('v4-range').onchange=()=>{const value=Number($('v4-range').value);if(Number.isFinite(value)&&value>=1&&value<=500){state.v4Scene.maxRange=value;render();}};
  $('v4-units').onchange=async()=>{if(!state.session)return;const confirmed=$('v4-units').checked;try{await api(`/api/v4/sessions/${state.session.id}/metadata`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({units:confirmed?'metres':'unknown',axes:confirmed?'x-forward-y-left-z-up':'unknown'})});await sessionChanged(state.session);render();}catch(error){status('v4-audit',error.message);}};
  globalThis.V4App={sessionChanged,selectionChanged,scan,status,get epoch(){return epoch;}};
  if(state.session)sessionChanged(state.session);
})();

// Load the next complete phase without changing the established editor source.
{const script=document.createElement('script');script.src='/static/camera-ui-v4.js';document.body.append(script);}

{const script=document.createElement('script');script.src='/static/quality-ui-v4.js';document.body.append(script);}

{const script=document.createElement('script');script.src='/static/scene-controls-v4.js';document.body.append(script);}

{const script=document.createElement('script');script.src='/static/automation-ui-v4.js';document.body.append(script);}

{const script=document.createElement('script');script.src='/static/backup-ui-v4.js';document.body.append(script);}

{const script=document.createElement('script');script.src='/static/session-save-v4.js';document.body.append(script);}

// Ground lifecycle fix: annotation refreshes do not change the point cloud.
(function(){
  let activeSession=state.session?.id??null;
  let desiredMode=state.v4Scene.mode;
  const originalSession=V4App.sessionChanged;
  V4App.sessionChanged=async function(data){
    const sameFrame=activeSession===data.id;
    const ground=sameFrame?state.v4Ground:null;
    const scene=sameFrame?{...state.v4Scene}:null;
    const groundStatus=sameFrame?$('v4-ground-status').textContent:'';
    activeSession=data.id;
    if(!sameFrame)desiredMode='raw';
    const refresh=originalSession(data);
    // The original hook resets synchronously, before fetching audit metadata.
    if(sameFrame){
      state.v4Ground=ground;state.v4Scene=scene;
      desiredMode=scene.mode;$('v4-ground-mode').value=desiredMode;
      $('v4-ground-status').textContent=groundStatus;
      render();
    }
    await refresh;
  };
  async function scanForMode(){
    const id=state.session?.id;if(!id)return;
    await V4App.scan();
    if(state.session?.id!==id)return;
    if(state.v4Ground){
      state.v4Scene.mode=desiredMode;
      $('v4-ground-mode').value=desiredMode;render();
    }
  }
  $('v4-ground-mode').onchange=async()=>{
    desiredMode=$('v4-ground-mode').value;
    state.v4Scene.mode=desiredMode;
    if(desiredMode!=='raw'&&!state.v4Ground){await scanForMode();return;}
    render();
  };
  $('v4-ground-run').onclick=async()=>{
    desiredMode=state.v4Scene.mode==='raw'?'dim':state.v4Scene.mode;
    await scanForMode();
  };
  const originalRaw=$('v4-raw').onclick;
  $('v4-raw').onclick=event=>{desiredMode='raw';originalRaw(event);};
})();

// Load depth rendering dependencies in a deterministic order.
(function(){
 if(typeof document==='undefined')return;
 const paths=['/static/solid-ground-math-v4.js','/static/solid-ground-gl-v4.js','/static/solid-ground-ui-v4.js'];
 function next(){const path=paths.shift();if(!path)return;const script=document.createElement('script');script.src=path;script.onload=next;script.onerror=()=>V4App.status('v4-ground-status','Không tải được ground renderer: '+path);document.body.append(script);}next();
})();
