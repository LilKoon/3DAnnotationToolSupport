/* Solid terrain controls and the main-view depth/picking integration. */
(function(){
 const options={allowBelow:false,xray:false,style:'data',fill:true,details:false,footprints:true,relative:false};
 const toolbar=document.querySelector('.v4-toolbar'),controls=document.createElement('details');controls.className='v4-solid-controls';
 controls.innerHTML=`<summary>Mặt đất đặc & góc nhìn</summary>
 <label>Bề mặt <select id="v4-solid-style"><option value="data">Theo dữ liệu ground</option><option value="reference">Sàn tham chiếu kín</option></select></label>
 <label><input type="checkbox" id="v4-solid-fill" checked> Nối lỗ nhỏ có ground bao quanh</label>
 <label><input type="checkbox" id="v4-solid-below"> Cho phép nhìn dưới mặt đất</label>
 <button id="v4-solid-upright">Về góc nhìn phía trên</button>
 <button id="v4-solid-xray" aria-pressed="false">X-ray: Tắt</button>
 <label><input type="checkbox" id="v4-solid-details"> Hiện nhãn và trục mọi box</label>
 <label><input type="checkbox" id="v4-solid-footprints" checked> Dấu chân box trên ground</label>
 <label><input type="checkbox" id="v4-solid-relative"> Lọc Z theo độ cao trên ground</label>
 <p id="v4-solid-status" role="status"></p>`;
 toolbar.after(controls);
 const warning=document.createElement('p');warning.id='v4-solid-orientation';warning.className='v4-solid-orientation';warning.setAttribute('role','status');controls.after(warning);
 for(const [id,key] of [['v4-solid-below','allowBelow'],['v4-solid-fill','fill'],['v4-solid-details','details'],['v4-solid-footprints','footprints'],['v4-solid-relative','relative']])$(id).onchange=()=>{options[key]=$(id).checked;render();};
 $('v4-solid-style').onchange=()=>{options.style=$('v4-solid-style').value;if(state.v4Scene.mode!=='surface'){$('v4-ground-mode').value='surface';$('v4-ground-mode').onchange();}render();};
 $('v4-solid-xray').onclick=()=>{options.xray=!options.xray;$('v4-solid-xray').setAttribute('aria-pressed',String(options.xray));$('v4-solid-xray').textContent='X-ray: '+(options.xray?'Bật':'Tắt');render();};
 $('v4-solid-upright').onclick=()=>{state.elevation=.68;options.allowBelow=false;$('v4-solid-below').checked=false;render();};
 let renderer=null,error=null,meshKey=null,meshStyle=null,meshFill=null,currentMesh={triangles:[],filled:0,reference:false},projected=[];
 function mesh(){
  if(meshKey!==state.v4Ground||meshStyle!==options.style||meshFill!==options.fill){currentMesh=SolidGroundMath.mesh(state.v4Ground,options.style,options.fill);meshKey=state.v4Ground;meshStyle=options.style;meshFill=options.fill;}
  return currentMesh;
 }
 function groundDepth(screen,g){
  if(state.v4Scene.mode!=='surface'||options.xray)return Infinity;
  let depth=Infinity;
  // Respect display clipping at the actual intersection, not just tile corners.
  for(const triangle of mesh().triangles){
   const t=triangle.map(g.project),d=SolidGroundMath.surfaceDepth([t],screen);if(!Number.isFinite(d)||d>=depth)continue;
   const c=Math.cos(state.yaw),s=Math.sin(state.yaw),e=Math.sin(state.elevation),v=Math.cos(state.elevation),uv=g.unproject(screen);
   const p=g.mid.map((value,i)=>value+[c,s,0][i]*uv.u+[-s*e,c*e,v][i]*uv.v+[-s*v,c*v,-e][i]*d);
   if(V4Scene.visible(p,-1,'main',state))depth=d;
  }
  return depth;
 }
 const previousRender=renderOne;
 renderOne=function(kind){
  if(kind!=='main'){previousRender(kind);return;}
  state.elevation=SolidGroundMath.clampElevation(state.elevation,options.allowBelow);
  const g=geometry(views.main,kind),m=mesh();
  warning.textContent=(state.elevation<0?'ĐANG NHÌN TỪ DƯỚI MẶT ĐẤT · mặt đáy màu nâu / sọc':'Đang nhìn phía trên · +Z hướng lên')+(options.xray?' · X-RAY: đang nhìn xuyên':'')+(m.reference&&state.v4Scene.mode==='surface'?' · SÀN THAM CHIẾU: chỉ hỗ trợ nhìn, không dùng đo':'');
  warning.classList.toggle('v4-solid-under',state.elevation<0);
  try{
   renderer??=new SolidGroundGL.DepthRenderer();
   const frameStart=performance.now();
   state.v4SolidStats=renderer.draw(g,state,m,options);
   state.v4SolidStats.render_ms=performance.now()-frameStart;
   projected=state.v4Scene.mode==='surface'?m.triangles.map(t=>t.map(g.project)):[];
   const visible=p=>options.xray||p.depth<=groundDepth(p,g)+.025;
   for(const box of state.session?.boxes||[]){
    const active=box.id===state.selected;if(box.status==='rejected'&&!active)continue;
    if(!V4Scene.visible(box.center,-1,'main',state))continue;
    const center=g.project(box.center);
    if((active||options.details||options.labels)&&visible(center)){g.ctx.font='12px ui-sans-serif,system-ui';g.ctx.fillStyle=active?'#f8f4c1':'#b9cbd4';g.ctx.fillText(box.label,center.x+6,center.y-7);}
    if(active&&state.mode==='edit')for(let axis=0;axis<3;axis++){if(!V4Scene.visible(axisEnd(box,axis),-1,'main',state))continue;const end=g.project(axisEnd(box,axis));if(!visible(end))continue;g.ctx.fillStyle=color['xyz'[axis]];g.ctx.beginPath();g.ctx.arc(end.x,end.y,6,0,Math.PI*2);g.ctx.fill();g.ctx.fillText('XYZ'[axis],end.x+8,end.y);}
   }
   const worldOrigin=g.project([0,0,0]);
   if(visible(worldOrigin))for(let axis=0;axis<3;axis++){const p=[0,0,0];p[axis]=10;const end=g.project(p);if(visible(end))drawLine(g.ctx,worldOrigin,end,color['xyz'[axis]],1);}
   // Fixed orientation widget stays readable even while panning/zooming.
   const origin={x:38,y:g.h-38},basis=Navigation3D.basis(state.yaw,state.elevation);
   for(let i=0;i<3;i++){const end={x:origin.x+basis.right[i]*24,y:origin.y-basis.up[i]*24};drawArrow(g.ctx,origin,end,color['xyz'[i]]);g.ctx.fillStyle=color['xyz'[i]];g.ctx.fillText('XYZ'[i],end.x+4,end.y);}
   $('v4-solid-status').textContent='WebGL · '+(options.xray?'X-ray':'che khuất theo chiều sâu')+' · '+m.triangles.length+' tam giác · nối '+m.filled+' ô nhỏ'+(options.relative?' · vùng thiếu ground vẫn giữ nguyên':'');
  }catch(e){
   error=e.message;state.v4SolidStats={renderer:'fallback',error};previousRender(kind);
   $('v4-solid-status').textContent='Không có che khuất: '+error+' · đang dùng renderer dự phòng.';
  }
 };
 const originalMove=moveDrag;moveDrag=function(event,kind){originalMove(event,kind);state.elevation=SolidGroundMath.clampElevation(state.elevation,options.allowBelow);};
 const originalHit=hitBox;
 hitBox=function(screen,kind,g){
  if(kind!=='main'||state.v4SolidStats?.renderer!=='webgl')return originalHit(screen,kind,g);
  const c=Math.cos(state.yaw),s=Math.sin(state.yaw),e=Math.sin(state.elevation),v=Math.cos(state.elevation),uv=g.unproject(screen),direction=[-s*v,c*v,-e],span=state.v4SolidStats.span;
  const origin=g.mid.map((value,i)=>value+[c,s,0][i]*uv.u+[-s*e,c*e,v][i]*uv.v-direction[i]*span);
  let best=null,distance=Infinity;const terrain=groundDepth(screen,g);
  for(const box of state.session?.boxes||[]){
   if(box.status==='rejected')continue;const t=SolidGroundMath.rayBox(origin,direction,box);if(t===null||t>=distance)continue;
   const p=origin.map((value,i)=>value+direction[i]*t);
   if(!V4Scene.visible(p,-1,'main',state)||t-span>terrain+.025)continue;
   best=box;distance=t;
  }
  return best;
 };
 const originalNearest=nearestPoint;
 nearestPoint=function(screen,g){
  if(state.v4SolidStats?.renderer!=='webgl')return originalNearest(screen,g);
  let best=null,distance=400;
  state.points.forEach((point,i)=>{if(!V4Scene.visible(point,i,'main',state))return;
   if(options.relative&&state.v4Ground){const z=SolidGroundMath.height(state.v4Ground,point);if(z!==null&&((state.v4Scene.zMin!==null&&point[2]-z<state.v4Scene.zMin)||(state.v4Scene.zMax!==null&&point[2]-z>state.v4Scene.zMax)))return;}
   const p=g.project(point),d=(p.x-screen.x)**2+(p.y-screen.y)**2;
   if(d<distance&&(options.xray||p.depth<=groundDepth(p,g)+.025)){distance=d;best=point;}
  });return best;
 };
 globalThis.V4Solid={options,mesh,groundDepth,get stats(){return state.v4SolidStats;},get error(){return error;}};
 render();
})();

(function(){
 const base=V4Scene.visible;
 V4Scene.visible=function(p,i,kind,s){
  if(!globalThis.V4Solid?.options.relative)return base(p,i,kind,s);
  if(!base(p,i,kind,{...s,v4Scene:{...s.v4Scene,zMin:null,zMax:null}}))return false;
  const ground=SolidGroundMath.height(s.v4Ground,p);if(ground===null)return true;
  const z=p[2]-ground;return (s.v4Scene.zMin===null||z>=s.v4Scene.zMin)&&(s.v4Scene.zMax===null||z<=s.v4Scene.zMax);
 };
})();

(function(){
 const button=document.createElement('button');button.id='v4-solid-snapshot';button.textContent='Xuất ảnh góc nhìn';$('v4-solid-status').before(button);
 button.onclick=()=>{
  const source=views.main,canvas=document.createElement('canvas');canvas.width=source.width;canvas.height=source.height+72;const ctx=canvas.getContext('2d');
  ctx.fillStyle='#112330';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.fillStyle='#deeee9';ctx.font='13px sans-serif';
  const caption=$('v4-solid-orientation').textContent;const words=caption.split(' ');let line='',y=20;
  for(const word of words){const candidate=line+word+' ';if(ctx.measureText(candidate).width>canvas.width-24){ctx.fillText(line,12,y);y+=18;line=word+' ';}else line=candidate;}ctx.fillText(line,12,y);
  ctx.drawImage(source,0,72);const link=document.createElement('a');link.download='v4-ground-view-'+Date.now()+'.png';link.href=canvas.toDataURL('image/png');link.textContent='Tải ảnh PNG';button.after(link);link.click();
 };
 const originalStart=startDrag;
 startDrag=function(event,kind){
  if(kind==='main'&&state.mode==='edit'&&!V4Solid.options.xray&&selected()){
   const g=geometry(views.main,'main'),screen=screenPos(event,views.main);
   for(let axis=0;axis<3;axis++){if(!SolidGroundMath.sideVisible(state.v4Ground,axisEnd(selected(),axis),state.elevation,V4Solid.options)){const hidden=g.project(axisEnd(selected(),axis));if(Math.hypot(hidden.x-screen.x,hidden.y-screen.y)<12){message('Tay nắm ở phía bị che. Bật X-ray hoặc đổi góc nhìn.',true);return;}}
    const p=g.project(axisEnd(selected(),axis));
    if(Math.hypot(p.x-screen.x,p.y-screen.y)<12&&p.depth>V4Solid.groundDepth(p,g)+.025){message('Tay nắm bị ground che. Bật X-ray hoặc đổi góc nhìn để chỉnh.',true);return;}}
  }
  originalStart(event,kind);
 };
})();

(function(){
 const previous=$('v4-solid-snapshot').onclick;
 $('v4-solid-snapshot').onclick=async()=>{
  if(!state.session)return;const id=state.session.id;
  previous();const link=$('v4-solid-snapshot').nextElementSibling;
  try{
   const result=await api('/api/v4/sessions/'+id+'/view-snapshot',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({png:link.href.split(',')[1]})});
   link.href=result.url;link.textContent='Tải ảnh PNG đã lưu';link.dataset.snapshotUrl=result.url;
   if(state.session?.id===id)message('Đã lưu ảnh góc nhìn cục bộ. Annotation giữ nguyên.');
  }catch(error){message('Lưu ảnh lỗi: '+error.message,true);}
 };
})();

(function(){
 const scan=$('v4-ground-run').onclick;
 $('v4-ground-run').onclick=()=>{
  if(state.v4Scene.mode==='raw'){$('v4-ground-mode').value='surface';return $('v4-ground-mode').onchange();}
  return scan();
 };
})();

(function(){
 const options=V4Solid.options;options.seal=true;
 const label=document.createElement('label');label.innerHTML='<input type="checkbox" id="v4-solid-seal" checked> Che toàn bộ phía đối diện';
 $('v4-solid-status').before(label);
 $('v4-solid-seal').onchange=()=>{options.seal=$('v4-solid-seal').checked;render();};
 const visible=V4Scene.visible;
 V4Scene.visible=function(p,i,kind,s){
  return visible(p,i,kind,s)&&(kind!=='main'||s.v4Scene.mode!=='surface'||SolidGroundMath.sideVisible(s.v4Ground,p,s.elevation,options));
 };
 const draw=renderOne;
 renderOne=function(kind){
  draw(kind);
  if(kind==='main'&&state.v4Scene.mode==='surface'&&options.seal&&!options.xray){
   $('v4-solid-status').textContent+=' · che toàn bộ phía đối diện';
   $('v4-solid-orientation').textContent+=' · phía đối diện đã ẩn (vùng thiếu ground dùng cao độ tham chiếu)';
  }
 };
 render();
})();

(function(){
 const options=V4Solid.options;options.floorOnly=true;
 const label=document.createElement('label');label.innerHTML='<input type="checkbox" id="v4-solid-floor-only" checked> Mặt đáy chỉ hiện sàn';
 $('v4-solid-status').before(label);
 $('v4-solid-floor-only').onchange=()=>{options.floorOnly=$('v4-solid-floor-only').checked;render();};
 const draw=renderOne;
 renderOne=function(kind){
  draw(kind);
  if(kind==='main'&&state.elevation<0&&state.v4Scene.mode==='surface'&&options.floorOnly&&!options.xray&&SolidGroundMath.referenceHeight(state.v4Ground)!==null){
   $('v4-solid-status').textContent+=' · mặt đáy chỉ hiện sàn';
   $('v4-solid-orientation').textContent+=' · điểm và box đã ẩn ở góc đáy; bật X-ray để xem';
  }
 };
 render();
})();

(function(){
 const options=V4Solid.options;options.labels=false;options.axes=false;options.details=false;
 const labelToggle=$('v4-solid-details'),label=labelToggle.parentElement;
 label.lastChild.textContent=' Hiện nhãn mọi object';
 labelToggle.onchange=()=>{options.labels=labelToggle.checked;render();};
 const axesLabel=document.createElement('label');
 axesLabel.innerHTML='<input type="checkbox" id="v4-solid-axes"> Hiện trục mọi object';
 label.after(axesLabel);
 $('v4-solid-axes').onchange=()=>{options.axes=$('v4-solid-axes').checked;render();};
 render();
})();

(function(){
 const model=document.createElement('script');model.src='/static/workspace-layout-model-v4.js';
 model.onload=()=>{const ui=document.createElement('script');ui.src='/static/workspace-layout-ui-v4.js';document.body.append(ui);};
 document.body.append(model);
})();
