(function(){
  state.v4Scene.maxRange=Infinity;$('v4-range').value='';$('v4-range').placeholder='Toàn bộ';
  const previous=$('v4-raw').onclick;$('v4-raw').onclick=()=>{previous();$('v4-range').value='';$('v4-z-min').value='';$('v4-z-max').value='';};
  $('v4-range').onchange=()=>{const value=$('v4-range').value.trim();if(value==='')state.v4Scene.maxRange=Infinity;else{const n=Number(value);if(!Number.isFinite(n)||n<1||n>500)return;state.v4Scene.maxRange=n;}render();};
  const toolbar=document.querySelector('.v4-toolbar');for(const [id,text,key] of [['v4-z-min','Z từ','zMin'],['v4-z-max','Z đến','zMax']]){const label=document.createElement('label');label.textContent=text+' ';const input=document.createElement('input');input.id=id;input.type='number';input.step='.1';input.placeholder='Tất cả';input.setAttribute('aria-label',text+' theo đơn vị dữ liệu');input.style.width='64px';input.onchange=()=>{const n=input.value===''?null:Number(input.value);if(n!==null&&!Number.isFinite(n))return;state.v4Scene[key]=n;render();};label.append(input);toolbar.append(label);}
  // Camera uploads can happen after opening a frame; refresh camera controls too.
  const originalCameras=renderCameras;renderCameras=function(){originalCameras();if(globalThis.V4Camera&&state.session)V4Camera.sessionChanged(state.session);};
  $('detect-mode').value='append';
})();

// Dynamic phase modules may arrive in either order; attach only after camera API exists.
globalThis.V4Controls={attachCameraHook(){const previous=renderCameras;renderCameras=function(){previous();if(state.session)V4Camera.sessionChanged(state.session);};}};
