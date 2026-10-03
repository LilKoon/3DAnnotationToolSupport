// UI for the two nuScenes models; use the existing cuboid editor and saver.
const guidelineLabels = ['car','truck','bus','trailer','construction_vehicle','pedestrian','motorcycle','bicycle','traffic_cone','barrier'];
const nuscenesModelIds = new Set(['pointpillars-nuscenes','centerpoint-nuscenes']);
let detectorUIInitialized = false;
let detectorDisabledControls = [];

function setDetectorBusy(busy) {
  if (busy) {
    const controls = [$('btn-add'), $('detect-mode'), $('detect-profile'), $('model'), $('threshold'), ...$('label-mapping').querySelectorAll('input,select'), ...$('editor').querySelectorAll('input,select,button')];
    detectorDisabledControls = controls.map(control => [control, control.disabled]);
    for (const control of controls) control.disabled = true;
  } else {
    for (const [control, disabled] of detectorDisabledControls) control.disabled = disabled;
    detectorDisabledControls = [];
  }
  updateReviewUI();
}

async function initDetectorUI() {
  if (detectorUIInitialized) return;
  detectorUIInitialized = true;
  const settings = await api('/api/detector/settings');
  $('gpu-mode').value = settings.mode;
  $('gpu-url').value = settings.url;
  $('gpu-intensity').value = settings.intensity_scale;
  if (settings.has_token) $('gpu-token').placeholder = 'Đã lưu token; để trống để giữ token khi URL không đổi';
  function modeChanged() {
    const local = $('gpu-mode').value !== 'remote';
    $('gpu-url').disabled = local;
    $('gpu-token').disabled = local;
  }
  $('gpu-mode').onchange = modeChanged;
  modeChanged();
  $('btn-gpu-save').onclick = async () => {
    const button = $('btn-gpu-save');
    button.disabled = true;
    $('gpu-status').textContent = 'Đang chạy xác minh model…';
    try {
      const saved = await api('/api/detector/settings', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({mode:$('gpu-mode').value, url:$('gpu-url').value, api_token:$('gpu-token').value || null, intensity_scale:Number($('gpu-intensity').value)})});
      $('gpu-token').value = '';
      $('gpu-token').placeholder = saved.has_token ? 'Token đã lưu; để trống để giữ khi URL không đổi' : 'Token worker';
      const checked = await api('/api/detector/check', {method:'POST'});
      $('gpu-status').textContent = checked.models.map(model => `${model.name}: ${model.reason}`).join(' · ');
      await loadModels();
    } catch (error) {
      $('gpu-status').textContent = error.message;
      fail(error);
    } finally { button.disabled = false; }
  };
  $('btn-guideline').onclick = async () => {
    if (!state.session || state.saving || state.detecting) return;
    try {
      const result = await api(`/api/sessions/${state.session.id}/guideline`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({revision:state.session.revision})});
      await openSession(result.id);
      message('Đã áp dụng đúng 10 nhãn DOCX. Geometry và trạng thái box được giữ lại.');
    } catch (error) { fail(error); }
  };
}

function updateDetectorHelp() {
  const spec = state.models?.find(model => model.id === $('model').value);
  $('model-help').textContent = spec ? `${spec.profile}. ${spec.reason || (spec.ready ? 'Sẵn sàng chạy.' : 'Cần cấu hình checkpoint và môi trường tương ứng.')}` : '';
  $('btn-detect').disabled = !state.session || !spec?.ready || !!state.detecting || !!state.saving;
  $('btn-guideline').hidden = !state.session || !!state.session.cvat || guidelineLabels.every(label => state.session.labels.includes(label));
  const area=$('label-coverage');area.replaceChildren();
  if(!state.session||!spec){$('auto-summary').textContent='Mở bài để tự nhận cấu hình nhãn.';return;}
  const mapping=currentMapping();
  const covered=state.session.labels.filter(label=>Object.values(mapping).includes(label));const unsupported=state.session.labels.filter(label=>!covered.includes(label));
  $('auto-summary').textContent=`Đã nhận cấu hình nhãn · ${covered.length}/${state.session.labels.length} nhãn có ánh xạ${unsupported.length?' · Chưa hỗ trợ/ánh xạ: '+unsupported.join(', '):''}.`;
  const title=document.createElement('p');title.textContent='Khả năng nhận diện theo nhãn job:';area.append(title);
  for(const label of state.session.labels){
    const sources=Object.entries(mapping).filter(([,target])=>target===label).map(([source])=>source);
    const line=document.createElement('p');line.textContent=`${label}: ${sources.length?'nhận đề xuất từ '+sources.join(', '):'chưa có lớp model ánh xạ; gắn thủ công hoặc chọn ánh xạ phù hợp'}`;area.append(line);
  }
  if(!Object.values(mapping).some(target=>target!=='__skip__'))$('btn-detect').disabled=true;
  if(spec) $('gpu-status').textContent=spec.reason||'';
}
