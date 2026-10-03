const $ = id => document.getElementById(id);
const views = {main: $('view-3d'), top: $('view-top'), front: $('view-front'), side: $('view-side')};
const state = {session:null, points:[], selected:null, yaw:-0.6, elevation:0.68, zoom:1, bounds:null, drag:null, saving:false};
Object.assign(state,{mainZoom:1,viewTarget:null,viewRange:null,mode:'orbit',projectionFocus:true});
const storedPointSize=Number(localStorage.getItem('cvat-point-size'));
state.pointSize=Number.isFinite(storedPointSize)&&storedPointSize>=.5&&storedPointSize<=6?storedPointSize:1.5;
const color = {x:'#f46d74', y:'#71d77c', z:'#5eb1ff'};
const reviewNames={pending:'Chờ duyệt',accepted:'Đã chấp nhận',rejected:'Đã từ chối'};
function updateReviewUI(){
  const boxes=state.session?.boxes||[],box=selected(),busy=state.saving||state.detecting||!!state.drag;
  const count=status=>boxes.filter(item=>item.status===status).length;
  $('review-summary').textContent=state.session?`${count('pending')} chờ · ${count('accepted')} chấp nhận · ${count('rejected')} từ chối`:'Chưa mở phiên.';
  $('btn-accept-all').textContent=`Chấp nhận tất cả đang chờ (${count('pending')})`;
  $('btn-accept-all').disabled=busy||!count('pending');
  $('review-selected').textContent=box?`${box.label} · ID ${box.id}`:'Chọn box để duyệt.';
  $('review-status').textContent=state.reviewing?'Đang lưu duyệt…':box?reviewNames[box.status]:'Chưa chọn box';
  $('review-status').className='review-badge'+(box?' status-'+box.status:'');
  for(const [id,status] of [['btn-accept','accepted'],['btn-reject','rejected'],['btn-pending','pending']]){
    $(id).disabled=busy||!box||box.status===status;$(id).setAttribute('aria-pressed',String(box?.status===status));
  }
  $('btn-delete-box').disabled=busy||!box;
}
async function reviewBoxes(status,bulk=false){
  if(!state.session||state.saving||state.detecting||state.drag)return;
  const targets=bulk?state.session.boxes.filter(box=>box.status==='pending'):selected()?[selected()]:[];
  if(!targets.length)return;
  if(bulk&&!confirm(`Chấp nhận ${targets.length} box đang chờ? Các box đã từ chối giữ nguyên. Kiểm tra annotation trước khi publish.`))return;
  const id=state.session.id,ids=new Set(targets.map(box=>box.id));
  const boxes=structuredClone(state.session.boxes);for(const box of boxes)if(ids.has(box.id))box.status=status;
  state.saving=true;state.reviewing=true;setDetectorBusy(true);updateReviewUI();$('save-state').textContent='Đang lưu duyệt…';
  try{
    const updated=await api(`/api/sessions/${id}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:state.session.revision,boxes})});
    if(state.session.id!==id)return;
    state.session={...state.session,...updated};populateEditor();renderList();render();$('save-state').textContent=`Đã lưu · r${updated.revision}`;
    message(bulk?`Đã chấp nhận ${targets.length} box đang chờ.`:`${reviewNames[status]} box ${targets[0].label}.`);
  }catch(error){$('save-state').textContent='Lưu duyệt lỗi';fail(error)}
  finally{state.saving=false;state.reviewing=false;setDetectorBusy(false);updateReviewUI()}
}

async function api(path, options={}) {
  const key = localStorage.getItem('v4_access_key');
  if (key) {
    options.headers = options.headers || {};
    options.headers['Authorization'] = `Bearer ${key}`;
  }
  const response = await fetch(path, options);
  if (response.status === 401) {
    if (typeof showAccessModal === 'function') showAccessModal(true);
    throw new Error('Yêu cầu Access Key (401)');
  }
  let result;
  try { result = await response.json(); } catch { throw new Error(`HTTP ${response.status}`); }
  if (!response.ok) throw new Error(CVATClient.errorMessage(result.detail,response.status));
  return result;
}
function message(text, error=false){clearTimeout(state.messageTimer);$('message').textContent=text;$('message').classList.toggle('error',error);if(!error)state.messageTimer=setTimeout(()=>{$('message').textContent=''},5000)}
function fail(error){message(error.message || String(error),true)}
function frameBox(box){return {x:box.center[0],y:box.center[1],z:box.center[2],sx:box.size[0],sy:box.size[1],sz:box.size[2]}}
function selected(){return state.session?.boxes.find(box=>box.id===state.selected)}
const axisOrders=[[0,1,2],[0,2,1],[1,0,2],[1,2,0],[2,0,1],[2,1,0]];
function initAxisControls(){for(const id of ['box-axis-order','session-axis-order'])for(const order of axisOrders){const option=document.createElement('option');option.value=order.join(',');option.textContent=order.map((geometric,i)=>`${'XYZ'[i]}=${['dài','rộng','cao'][geometric]}`).join(' · ');$(id).append(option)}}
function populateAxisConvention(){const convention=state.session?.axis_convention||{axis_order:[0,1,2],axis_signs:[1,1,1]};$('session-axis-order').value=convention.axis_order.join(',');for(let i=0;i<3;i++)$('session-sign-'+'xyz'[i]).value=String(convention.axis_signs[i]);$('btn-session-axes').disabled=!state.session;$('btn-apply-axes').disabled=!state.session;}
async function saveAxisConvention(apply_existing){if(!state.session||state.saving||state.detecting||state.drag)return;const count=state.session.boxes.length;if(apply_existing&&!confirm(`Áp dụng quy ước trục này cho ${count} box hiện có? Tâm, kích thước và yaw giữ nguyên. Có thể chọn lại quy ước khác.`))return;const sessionId=state.session.id,convention={axis_order:$('session-axis-order').value.split(',').map(Number),axis_signs:[... 'xyz'].map(axis=>Number($('session-sign-'+axis).value))};state.saving=true;try{const updated=await api(`/api/sessions/${sessionId}/axis-convention`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:state.session.revision,convention,apply_existing})});if(state.session.id!==sessionId)return;state.session={...state.session,...updated};populateAxisConvention();populateEditor();renderList();render();$('save-state').textContent=`Đã lưu · r${updated.revision}`;message(apply_existing?`Đã áp dụng trục cho ${count} box và các box mới.`:'Đã lưu trục mặc định cho box mới, kể cả auto-detect.')}catch(error){fail(error)}finally{state.saving=false;updateReviewUI()}}
function point(x,y,z){return [x,y,z]}
function corners(box){return CuboidEdit.corners(box)}
const edges=[[0,1],[0,2],[1,3],[2,3],[4,5],[4,6],[5,7],[6,7],[0,4],[1,5],[2,6],[3,7]];
function bounds(points){
  const mins=[Infinity,Infinity,Infinity],maxs=[-Infinity,-Infinity,-Infinity];
  for(const p of points) for(let i=0;i<3;i++){mins[i]=Math.min(mins[i],p[i]);maxs[i]=Math.max(maxs[i],p[i]);}
  if(!points.length) return {mid:[0,0,0],range:30};
  return {mid:mins.map((v,i)=>(v+maxs[i])/2),range:Math.max(10,...mins.map((v,i)=>maxs[i]-v))*1.12};
}
function geometry(canvas,kind){
  const rect=canvas.getBoundingClientRect(),dpr=window.devicePixelRatio||1;
  if(canvas.width!==Math.round(rect.width*dpr)||canvas.height!==Math.round(rect.height*dpr)){canvas.width=Math.round(rect.width*dpr);canvas.height=Math.round(rect.height*dpr)}
  const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);
  const w=rect.width,h=rect.height,active=kind==='main'?null:selected();
  const b=kind==='main'?{mid:state.viewTarget||state.bounds?.mid||[0,0,0],range:state.viewRange||state.bounds?.range||30}:active?{mid:active.center,range:Math.max(6,...active.size.map(v=>v*3))}:state.bounds||{mid:[0,0,0],range:30};
  const scale=active&&state.projectionFocus?ProjectionFocus.fitScale(active,kind,w,h)*state.zoom:Math.min(w,h)/(b.range*(kind==='main'?.95:.86))*(kind==='main'?state.mainZoom:state.zoom);
  function project(p){let u,v,depth=0;const x=p[0]-b.mid[0],y=p[1]-b.mid[1],z=p[2]-b.mid[2];
    if(kind==='top'){u=x;v=y}else if(kind==='front'){u=x;v=z}else if(kind==='side'){u=y;v=z}else{
      const c=Math.cos(state.yaw),s=Math.sin(state.yaw),e=state.elevation,side=-x*s+y*c;
      u=x*c+y*s;v=side*Math.sin(e)+z*Math.cos(e);depth=side*Math.cos(e)-z*Math.sin(e);
    }
    return {x:w/2+u*scale,y:h/2-v*scale,depth};
  }
  function unproject(screen){return {u:(screen.x-w/2)/scale,v:-(screen.y-h/2)/scale};}
  return {ctx,w,h,scale,project,unproject,mid:b.mid};
}
function drawLine(ctx,a,b,stroke,width=1){ctx.strokeStyle=stroke;ctx.lineWidth=width;ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke()}
function drawArrow(ctx,a,b,stroke){drawLine(ctx,a,b,stroke,2);const ang=Math.atan2(b.y-a.y,b.x-a.x);for(const side of [-1,1])drawLine(ctx,b,{x:b.x-7*Math.cos(ang+side*.5),y:b.y-7*Math.sin(ang+side*.5)},stroke,2)}
function axisEnd(box,axis){const geometric=(box.axis_order||[0,1,2])[axis],length=Math.max(.55,box.size[geometric]*.65),direction=Navigation3D.objectAxis(box,axis);return box.center.map((v,i)=>v+direction[i]*length)}
function renderOne(kind){
  const g=geometry(views[kind],kind),{ctx,w,h,project}=g;ctx.fillStyle='#0f1924';ctx.fillRect(0,0,w,h);if(globalThis.V4Scene)V4Scene.drawSurface(g,kind,state);

  ctx.fillStyle=kind==='main'?'rgba(202,220,222,.67)':'rgba(207,222,225,.6)';
  const stride=kind==='main'?1:Math.max(1,Math.ceil(state.points.length/45000));
  const focused=kind!=='main'&&state.projectionFocus&&selected();
  for(let i=0;i<state.points.length;i+=stride){if(focused&&!ProjectionFocus.nearBox(state.points[i],focused,kind))continue;if(globalThis.V4Scene&&!V4Scene.visible(state.points[i],i,kind,state))continue;const p=project(state.points[i]);if(p.x>=0&&p.x<w&&p.y>=0&&p.y<h){const rgb=state.pointColors?.[i];ctx.globalAlpha=globalThis.V4Scene?V4Scene.alpha(i,state):1;ctx.fillStyle=state.pointColorMode!=='uniform'&&rgb?`rgb(${rgb[0]},${rgb[1]},${rgb[2]})`:kind==='main'?'rgba(202,220,222,.67)':'rgba(207,222,225,.6)';ctx.fillRect(p.x-state.pointSize/2,p.y-state.pointSize/2,state.pointSize,state.pointSize)}}
  ctx.globalAlpha=1;
  for(const box of state.session?.boxes||[]){
    const active=box.id===state.selected;
    if(focused&&!active)continue;
    if(box.status==='rejected'&&!active)continue;
    const jobColor=state.session.label_specs?.find(spec=>spec.name===box.label)?.color;
    const stroke=box.status==='rejected'?'#f08b8b':/^#[0-9a-f]{6}$/i.test(jobColor||'')?jobColor:box.status==='accepted'?'#52d4ab':'#e99b60',pts=kind!=='main'&&active?projectionHandles(box,kind,g).filter(handle=>handle.kind==='resize'):corners(box).map(project);
    ctx.setLineDash(box.status==='rejected'?[5,4]:[]);
    if(kind==='main'){for(const [a,b] of edges)drawLine(ctx,pts[a],pts[b],stroke,active?2:1.4)}
    else{const outline=ProjectionFocus.hull(pts);ctx.beginPath();outline.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.closePath();if(active){ctx.fillStyle=stroke+'26';ctx.fill()}ctx.strokeStyle=active?'#e4edf3':stroke;ctx.lineWidth=active?2:1;ctx.stroke();}
    ctx.setLineDash([]);
    const center=project(box.center);
    if(kind==='main')for(let axis=0;axis<3;axis++){
      const end=project(axisEnd(box,axis));drawArrow(ctx,center,end,color['xyz'[axis]]);
      if(active&&kind==='main'&&state.mode==='edit'){ctx.fillStyle=color['xyz'[axis]];ctx.beginPath();ctx.arc(end.x,end.y,6,0,Math.PI*2);ctx.fill();ctx.fillText('XYZ'[axis],end.x+8,end.y)}
    }
    if(kind==='main'){ctx.font='12px ui-sans-serif,system-ui';ctx.fillStyle=stroke;ctx.fillText(box.label,center.x+6,center.y-7);}

    if(active&&kind!=='main')for(const handle of projectionHandles(box,kind,g)){ctx.beginPath();ctx.arc(handle.x,handle.y,handle.kind==='rotate'?5:4,0,Math.PI*2);ctx.fillStyle=handle.kind==='rotate'?'#4ed58c':'#ff6268';ctx.fill()}
  }
  if (kind === 'main') {
    const origin=project([0,0,0]);
    for(let axis=0;axis<3;axis++){const p=[0,0,0];p[axis]=10;drawLine(ctx,origin,project(p),color['xyz'[axis]],1);}
  }
}
function render(){if(state.renderPending)return;state.renderPending=true;requestAnimationFrame(()=>{state.renderPending=false;for(const kind of Object.keys(views))renderOne(kind)})}
function projectionHandles(box,kind,g){
  const basis=CuboidEdit.basis(box),horizontal=kind==='side'?1:0,vertical=kind==='top'?1:2;
  const first=kind==='top'?0:Math.abs(basis[0][horizontal]*basis[2][vertical]-basis[2][horizontal]*basis[0][vertical])>=Math.abs(basis[1][horizontal]*basis[2][vertical]-basis[2][horizontal]*basis[1][vertical])?0:1;
  const axes=kind==='top'?[0,1]:[first,2],out=[];
  for(const a of [-1,1])for(const b of [-1,1]){const p=box.center.map((v,i)=>v+basis[axes[0]][i]*a*box.size[axes[0]]/2+basis[axes[1]][i]*b*box.size[axes[1]]/2);out.push({...g.project(p),kind:'resize',axes,signs:[a,b]})}
  const center=g.project(box.center);
  out.push({x:center.x,y:Math.max(12,Math.min(...out.map(p=>p.y))-16),kind:'rotate'});return out;
}
function hitBox(screen,kind,g){const boxes=[...(state.session?.boxes||[])].reverse();
  for(const box of boxes){if(kind!=='main'&&state.projectionFocus&&selected()&&box.id!==state.selected)continue;if(box.status==='rejected')continue;const pts=corners(box).map(g.project);const xs=pts.map(p=>p.x),ys=pts.map(p=>p.y);if(screen.x>=Math.min(...xs)-6&&screen.x<=Math.max(...xs)+6&&screen.y>=Math.min(...ys)-6&&screen.y<=Math.max(...ys)+6)return box}
  return null;
}
function pickHandle(screen,box,kind,g){
  for(const handle of projectionHandles(box,kind,g))if(Math.hypot(screen.x-handle.x,screen.y-handle.y)<11)return handle;
  return {kind:'move'};
}
function screenPos(event,canvas){const r=canvas.getBoundingClientRect();return {x:event.clientX-r.left,y:event.clientY-r.top}}
function setNavigationMode(mode){state.mode=mode;document.querySelectorAll('[data-mode]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.mode===mode)));$('navigation-help').textContent=mode==='edit'?'Kéo đầu mũi tên X/Y/Z để di chuyển theo trục · Kéo thân box: di chuyển trong mặt phẳng màn hình · Shift+kéo: dịch góc nhìn':mode==='add'?'Click gần điểm LiDAR để đặt box tại đó · Double-click điểm: lấy tâm · Cuộn/pinch: zoom':'Kéo: '+(mode==='pan'?'dịch góc nhìn':'xoay, kể cả trên box')+' · Shift+kéo hoặc chuột phải: dịch · Cuộn/pinch: zoom · Double-click điểm: lấy tâm';render()}
function focusAt(center,range){state.viewTarget=[...center];state.viewRange=range;state.mainZoom=1;render()}
function nearestPoint(screen,g){let best=null,distance=20*20;for(const [i,p] of state.points.entries()){if(globalThis.V4Scene&&!V4Scene.visible(p,i,'main',state))continue;const projected=g.project(p),d=(projected.x-screen.x)**2+(projected.y-screen.y)**2;if(d<distance){distance=d;best=p}}return best}
async function addBoxAt(center){if(!state.session||state.saving||state.detecting)return;const box={id:crypto.randomUUID(),frame:state.session.cvat?.frame||0,label:state.session.labels[0]||'Object',center:[...center.slice(0,3)],size:[3,1.8,1.5],yaw:0,...structuredClone(state.session.axis_convention||{axis_order:[0,1,2],axis_signs:[1,1,1]}),source:'manual',status:'pending',confidence:null};state.session.boxes.push(box);select(box.id);await save();setNavigationMode('edit');message('Đã đặt box tại vị trí đang xem. Kéo XYZ hoặc chỉnh trong Top/Front/Side.');}
function startDrag(event,kind){if(!state.session)return;if(state.saving&&kind!=='main')return;if(state.detecting&&kind!=='main'){message('Chờ model hoàn tất trước khi kéo sửa box.');return}const canvas=views[kind],g=geometry(canvas,kind),screen=screenPos(event,canvas),box=selected();
  if(kind==='main'){
    event.preventDefault();canvas.focus();
    const pan=event.shiftKey||event.button===2||event.button===1||state.mode==='pan';
    const picked=hitBox(screen,kind,g);
    if(!pan&&state.mode==='add'){const p=nearestPoint(screen,g);if(p)addBoxAt(p);else message('Click gần một điểm LiDAR để đặt box chính xác.',true);return}
    let handle=null,target=box;
    if(!pan&&state.mode==='edit'&&!state.detecting&&!state.saving){
      if(box)for(let axis=0;axis<3;axis++){const end=g.project(axisEnd(box,axis));if(Math.hypot(end.x-screen.x,end.y-screen.y)<12){handle={kind:'axis',axis};break}}
      if(!handle&&picked){target=picked;select(target.id);handle={kind:'plane'}}
    }
    state.drag={kind:handle?'main':pan?'pan':'orbit',handle,boxId:handle?target.id:null,initial:handle?structuredClone(target):null,start:screen,scale:g.scale,yaw:state.yaw,elevation:state.elevation,target:[...(state.viewTarget||g.mid)],picked:picked?.id,moved:false};
    canvas.setPointerCapture(event.pointerId);return;
  }
  let hit=box&&pickHandle(screen,box,kind,g),target=box;
  if(!hit||hit.kind==='move'){const candidate=hitBox(screen,kind,g);if(candidate){target=candidate;select(candidate.id);hit=pickHandle(screen,target,kind,g)}else{target=null;hit=null}}
  if(!target){message('Chọn box trong danh sách rồi kéo phần thân hoặc tay nắm trên hình chiếu.');return}
  state.drag={kind,handle:hit||{kind:'move'},boxId:target.id,start:screen,rotationCenter:g.project(target.center),initial:structuredClone(target),scale:g.scale,moved:false};canvas.setPointerCapture(event.pointerId);
  message(`Đang chỉnh ${target.label} trong ${kind.toUpperCase()}…`);
}
function moveDrag(event,kind){const drag=state.drag;if(!drag||drag.kind!==kind&&!(kind==='main'&&['orbit','pan'].includes(drag.kind)))return;const screen=screenPos(event,views[kind]);
  const px=screen.x-drag.start.x,py=screen.y-drag.start.y;drag.moved ||= Math.hypot(px,py)>3;if(!drag.moved)return;
  if(drag.kind==='orbit'){state.yaw=drag.yaw+(screen.x-drag.start.x)*.008;state.elevation=Math.max(-1.4,Math.min(1.4,drag.elevation+(screen.y-drag.start.y)*.008));render();return}
  if(drag.kind==='pan'){const delta=Navigation3D.screenDelta(px,py,drag.scale,drag.yaw,drag.elevation);state.viewTarget=drag.target.map((v,i)=>v-delta[i]);render();return}
  const box=selected();if(!box||box.id!==drag.boxId)return;const dx=(screen.x-drag.start.x)/drag.scale,dy=-(screen.y-drag.start.y)/drag.scale,initial=drag.initial;
  if(kind==='main'){
    if(drag.handle.kind==='axis'){const direction=Navigation3D.objectAxis(initial,drag.handle.axis),distance=Navigation3D.axisDelta(px,py,direction,drag.scale,drag.yaw,drag.elevation);box.center=initial.center.map((v,i)=>v+direction[i]*distance)}
    else {const delta=Navigation3D.screenDelta(px,py,drag.scale,drag.yaw,drag.elevation);box.center=initial.center.map((v,i)=>v+delta[i])}
  }else if(drag.handle.kind==='rotate'){
    const center=drag.rotationCenter,angle=Math.atan2(-(screen.y-center.y),screen.x-center.x)-Math.atan2(-(drag.start.y-center.y),drag.start.x-center.x);
    Object.assign(box,CuboidEdit.rotate(initial,kind,angle));
  }else if(drag.handle.kind==='resize'){
    const resized=CuboidEdit.resize(initial,drag.handle.axes,drag.handle.signs,[dx,dy],kind);
    if(resized)Object.assign(box,resized);else message('Mặt box đang gần vuông góc với khung này. Chỉnh ở hình chiếu khác hoặc nhập số.',true);
  }else if(kind==='top'){box.center[0]=initial.center[0]+dx;box.center[1]=initial.center[1]+dy}
  else if(kind==='front'){box.center[0]=initial.center[0]+dx;box.center[2]=initial.center[2]+dy}
  else {box.center[1]=initial.center[1]+dx;box.center[2]=initial.center[2]+dy}
  populateEditor();render();
}
async function endDrag(event){if(!state.drag)return;const drag=state.drag;state.drag=null;
  if(event?.type==='pointercancel'){if(drag.initial){const box=selected();if(box&&box.id===drag.boxId)Object.assign(box,drag.initial);populateEditor();render()}return}
  if(!drag.moved){if(drag.picked)select(drag.picked);return}
  if(!['orbit','pan'].includes(drag.kind)){await save();message('Đã lưu vị trí và kích thước box.')}
}
function select(id){if(state.selected!==id)state.zoom=1;state.selected=id;$('projection-hint').textContent=state.projectionFocus&&selected()?`${selected().label} · chỉ vùng quanh box`:'Toàn cảnh hình chiếu';populateEditor();renderList();render();if(globalThis.V4App)V4App.selectionChanged()}
function populateEditor(){updateReviewUI();const box=selected();$('editor').hidden=!box;$('empty-selection').hidden=!!box;$('btn-focus-box').disabled=!box;if(!box)return;
  $('edit-label').value=box.label;
  for(let i=0;i<3;i++){$('center-'+'xyz'[i]).value=box.center[i].toFixed(2);$('size-'+'xyz'[i]).value=box.size[i].toFixed(2)}
  for(const angle of ['yaw','pitch','roll'])$(angle).value=((box[angle]||0)*180/Math.PI).toFixed(1);
  const order=box.axis_order||[0,1,2];$('box-axis-order').value=order.join(',');
  const dimensions=['dài','rộng','cao'];$('axis-values').textContent=order.map((geometric,i)=>`${'XYZ'[i]} → ${box.axis_signs[i]>0?'+':'−'}${dimensions[geometric]}`).join(' · ');
  let handedness=box.axis_signs.reduce((value,sign)=>value*sign,1);for(let i=0;i<3;i++)for(let j=i+1;j<3;j++)if(order[i]>order[j])handedness*=-1;
  $('axis-publish-hint').textContent=handedness<0?'Hệ trục tay trái: CVAT không biểu diễn được bằng góc xoay. Bấm Đảo X, Y hoặc Z để đổi sang hệ tay phải trước khi publish.':'Trục sẽ được chuyển thành góc xoay và kích thước thật trên CVAT, giữ nguyên hình dạng box.';
  $('axis-publish-hint').style.color=handedness<0?'#f08b8b':'';
}
function renderList(){updateReviewUI();const boxes=state.session?.boxes||[];$('count').textContent=boxes.length;const list=$('objects');list.replaceChildren();
  for(const box of boxes){const button=document.createElement('button');button.className='object-item'+(box.id===state.selected?' selected':'');button.setAttribute('aria-pressed',String(box.id===state.selected));const name=document.createElement('span');name.textContent=box.label;const status=document.createElement('small');status.className='status-'+box.status;status.textContent=reviewNames[box.status]+(box.confidence!=null?` · ${(box.confidence*100).toFixed(0)}%`:'');button.append(name,status);button.onclick=()=>select(box.id);list.append(button)}
  const archived=state.session?.deleted_boxes||[];$('deleted-count').textContent=archived.length;$('deleted-objects').replaceChildren();
  for(const box of archived){const row=document.createElement('div');row.className='deleted-item';const label=document.createElement('span');label.textContent=box.label;const button=document.createElement('button');button.textContent='Khôi phục';button.setAttribute('aria-label',`Khôi phục ${box.label} ${box.id}`);button.onclick=()=>archiveSelected(box,true);row.append(label,button);$('deleted-objects').append(row)}
}
async function archiveSelected(box=selected(),restore=false){if(!box||!state.session||state.saving||state.detecting||state.drag)return;
  if(!restore&&!confirm(`Xoá box ${box.label}\nID: ${box.id}\nKhỏi danh sách đang gắn nhãn? Box được giữ trong “Box đã xoá” và có thể khôi phục. Không xoá dữ liệu trên CVAT.`))return;
  const id=state.session.id;state.saving=true;setDetectorBusy(true);updateReviewUI();$('save-state').textContent='Đang lưu…';try{const updated=await api(`/api/sessions/${id}/boxes/${encodeURIComponent(box.id)}/archive`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:state.session.revision,restore})});if(state.session.id!==id)return;state.session={...state.session,...updated};state.selected=restore?box.id:(updated.boxes.find(item=>item.status!=='rejected')||updated.boxes[0])?.id||null;populateEditor();renderList();render();$('save-state').textContent=`Đã lưu · r${updated.revision}`;message(restore?'Đã khôi phục box.':'Đã xoá box khỏi bản nháp. Có thể lấy lại trong Box đã xoá.')}catch(error){fail(error)}finally{state.saving=false;setDetectorBusy(false);updateReviewUI()}}
async function save(){if(!state.session)return;state.pendingSave=true;if(state.saving)return;state.saving=true;$('save-state').textContent='Đang lưu…';try{while(state.pendingSave){state.pendingSave=false;const revision=state.session.revision,boxes=structuredClone(state.session.boxes),id=state.session.id;const updated=await api(`/api/sessions/${id}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision,boxes})});state.session.revision=updated.revision;$('save-state').textContent=`Đã lưu · r${updated.revision}`;renderList()}}catch(error){$('save-state').textContent='Lưu lỗi';fail(error)}finally{state.saving=false;updateReviewUI()}}
function renderCameras(){const list=$('camera-list');list.replaceChildren();for(const camera of state.session?.cameras||[]){const label=document.createElement('small');label.textContent=camera.name;const img=document.createElement('img');img.alt=`Camera ${camera.name}`;img.src=`/api/sessions/${state.session.id}/cameras/${camera.index}?access_key=${localStorage.getItem('v4_access_key')||''}`;list.append(label,img)}}
function renderMapping(){
  const area=$('label-mapping');area.replaceChildren();area.hidden=!state.session;if(!state.session)return;
  const spec=state.models?.find(item=>item.id===$('model').value);
  const key=`${detectorPreferenceKey()}:${spec?.id}`;const preferences=readDetectorPreferences();state.labelMaps??={};
  for(const source of spec?.classes||[]){
    const label=document.createElement('label');label.textContent=`${source} → nhãn phiên`;
    const select=document.createElement('select');select.dataset.source=source;
    const skip=document.createElement('option');skip.value='__skip__';skip.textContent='Bỏ qua';select.append(skip);
    for(const name of state.session.labels){
      const option=document.createElement('option');option.value=name;option.textContent=name;select.append(option);
    }
    const saved=state.session.detection?.model_id===spec?.id?state.session.detection:null;
    const target=state.labelMaps[key]?.[source]??preferences.mapping?.[source]??saved?.mapping?.[source.toLowerCase()]??LabelMapping.defaultTarget(source,state.session.labels);
    select.value=[...select.options].some(option=>option.value===target)?target:'__skip__';
    select.onchange=()=>{state.labelMaps[key]??={};state.labelMaps[key][source]=select.value;saveDetectorPreferences();updateDetectorHelp()};
    const threshold=document.createElement('input');threshold.type='number';threshold.min='0';threshold.max='1';threshold.step='.05';threshold.placeholder='Ngưỡng chung';threshold.dataset.thresholdSource=source;threshold.setAttribute('aria-label',`Ngưỡng confidence cho ${source}`);
    state.classThresholds??={};threshold.value=state.classThresholds[key]?.[source]??saved?.class_thresholds?.[source.toLowerCase()]??'';
    threshold.onchange=()=>{state.classThresholds[key]??={};state.classThresholds[key][source]=threshold.value;$('detect-profile').value='custom';saveDetectorPreferences();updateProfileUI()};
    label.append(select,threshold);area.append(label);
  }
  updateDetectorHelp();
}
function currentMapping(){return Object.fromEntries([...$('label-mapping').querySelectorAll('select')].map(select=>[select.dataset.source,select.value]))}
async function openSession(id){const data=await api(`/api/sessions/${id}`);if(state.session?.id!==id){state.mainZoom=1;state.viewTarget=null;state.viewRange=null;state.zoom=1;state.yaw=-.6;state.elevation=.68;state.evaluation=null;$('evaluation-results').replaceChildren();$('evaluation-frames').replaceChildren();$('evaluation-complete').checked=false;$('btn-apply-recommendation').hidden=true;$('evaluation-status').textContent=''}state.session=data;if(globalThis.V4App)V4App.sessionChanged(data);if(data.cvat){$('cvat-url').value=data.cvat.url;$('cvat-job').value=data.cvat.job_id;}state.points=data.points;state.pointColors=data.point_colors||null;$('point-color-hint').textContent=state.pointColors?'Có RGB gốc':'File không có RGB; dùng màu sáng';state.bounds=bounds(state.points);state.selected=null;$('session-title').textContent=data.title;$('point-count').textContent=`${state.points.length.toLocaleString()} điểm hiển thị`;$('btn-add').disabled=false;$('btn-export').disabled=false;$('btn-publish').disabled=!data.cvat;$('btn-detect').disabled=!$('model').selectedOptions[0]?.dataset.ready;const labels=$('edit-label');labels.replaceChildren();for(const name of data.labels){const option=document.createElement('option');option.value=name;option.textContent=name;labels.append(option)}history.replaceState(null,'',`/?session=${id}`);localStorage.setItem('cvat-v4-last-session', id);populateAxisConvention();renderList();renderCameras();restoreDetectorPreferences();renderMapping();populateEditor();renderDetectionReport();render();$('save-state').textContent=`Đã tải · r${data.revision}`}
function credentials() {
  const loginHidden = $('cvat-login-form').style.display === 'none';
  return {
    url: loginHidden ? (localStorage.getItem('v4_cvat_url') || $('cvat-url').value) : $('cvat-url').value,
    username: loginHidden ? (localStorage.getItem('v4_cvat_user') || $('cvat-user').value) : $('cvat-user').value,
    password: loginHidden ? (localStorage.getItem('v4_cvat_pass') || $('cvat-pass').value) : $('cvat-pass').value,
    job_id: Number($('cvat-job').value),
    verify_ssl: true
  };
}
async function loadModels(){
  try{
    await initDetectorUI();
    const previous=$('model').value;
    const models=(await api('/api/models')).filter(model=>nuscenesModelIds.has(model.id)||model.id==='geometry-cpu');
    state.models=models;$('model').replaceChildren();
    for(const model of models){const option=document.createElement('option');option.value=model.id;option.dataset.ready=String(model.ready);option.textContent=`${model.name}${model.ready?' · sẵn sàng':' · cần cấu hình'}`;$('model').append(option)}
    if(models.some(model=>model.id===previous))$('model').value=previous;
    $('model').onchange=()=>{renderMapping();saveDetectorPreferences()};restoreDetectorPreferences();renderMapping();
  }catch(error){fail(error)}
}
function zoomMain(factor,screen=null){const g=geometry(views.main,'main');state.mainZoom=Math.max(.05,Math.min(100,state.mainZoom*factor));if(screen){const newScale=geometry(views.main,'main').scale,a=Navigation3D.screenDelta(screen.x-g.w/2,screen.y-g.h/2,g.scale,state.yaw,state.elevation),b=Navigation3D.screenDelta(screen.x-g.w/2,screen.y-g.h/2,newScale,state.yaw,state.elevation);state.viewTarget=g.mid.map((v,i)=>v+a[i]-b[i])}render()}
for(const [kind,canvas] of Object.entries(views)){canvas.addEventListener('pointerdown',event=>startDrag(event,kind));canvas.addEventListener('pointermove',event=>moveDrag(event,kind));canvas.addEventListener('pointerup',endDrag);canvas.addEventListener('pointercancel',endDrag);canvas.addEventListener('contextmenu',event=>event.preventDefault());canvas.addEventListener('wheel',event=>{event.preventDefault();if(state.drag)return;if(kind==='main'){if(event.shiftKey){const g=geometry(canvas,kind),delta=Navigation3D.screenDelta(event.deltaX||event.deltaY,0,g.scale,state.yaw,state.elevation);state.viewTarget=g.mid.map((v,i)=>v+delta[i]);render()}else zoomMain(Math.exp(-Math.max(-300,Math.min(300,event.deltaY))*.003),screenPos(event,canvas))}else{state.zoom=Math.max(.1,Math.min(50,state.zoom*Math.exp(-Math.max(-300,Math.min(300,event.deltaY))*.003)));render()}},{passive:false})}
views.main.addEventListener('dblclick',event=>{if(!state.session)return;const p=nearestPoint(screenPos(event,views.main),geometry(views.main,'main'));if(p){focusAt(p.slice(0,3),Math.min(15,state.viewRange||state.bounds.range));message('Đã lấy tâm tại điểm LiDAR. Có thể xoay quanh vùng này và đặt box.')}else message('Double-click gần một điểm LiDAR để lấy tâm.',true)});
document.querySelectorAll('[data-mode]').forEach(button=>button.onclick=()=>setNavigationMode(button.dataset.mode));
$('btn-focus-box').onclick=()=>{const box=selected();if(box)focusAt(box.center,Math.max(6,...box.size.map(value=>value*3)))};
$('btn-zoom-in').onclick=()=>zoomMain(1.3);$('btn-zoom-out').onclick=()=>zoomMain(1/1.3);
views.main.addEventListener('keydown',event=>{const modes={o:'orbit',p:'pan',e:'edit',n:'add'};if(event.ctrlKey||event.metaKey||event.altKey)return;const key=event.key.toLowerCase();if(modes[key]){event.preventDefault();setNavigationMode(modes[key])}else if(key==='f'){event.preventDefault();$('btn-focus-box').click()}else if(['+','=','-'].includes(key)){event.preventDefault();zoomMain(key==='-'?1/1.3:1.3)}else if(key==='delete'||key==='backspace'){event.preventDefault();archiveSelected()}else if(event.key.startsWith('Arrow')){event.preventDefault();const g=geometry(views.main,'main'),dx=event.key==='ArrowLeft'?-30:event.key==='ArrowRight'?30:0,dy=event.key==='ArrowUp'?-30:event.key==='ArrowDown'?30:0,delta=Navigation3D.screenDelta(dx,dy,g.scale,state.yaw,state.elevation);state.viewTarget=g.mid.map((v,i)=>v+delta[i]);render()}});
window.addEventListener('resize',render);
$('btn-reset-view').onclick=()=>{state.yaw=-.6;state.elevation=.68;state.zoom=1;state.mainZoom=1;state.viewTarget=null;state.viewRange=null;render()};
$('file').onchange=async event=>{const file=event.target.files[0];if(!file)return;try{message('Đang đọc point cloud…');const result=await api(`/api/sessions/upload?filename=${encodeURIComponent(file.name)}`,{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:file});await openSession(result.id);message('Đã mở point cloud. Có thể thêm box hoặc chạy model.') }catch(error){fail(error)}};
$('btn-demo').onclick=async()=>{try{const result=await api('/api/sessions/demo',{method:'POST'});await openSession(result.id);message('Demo 3D đã mở. Kéo box trong Top/Front/Side để chỉnh.') }catch(error){fail(error)}};
$('btn-frames').onclick=async()=>{try{const result=await api('/api/cvat/job',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(credentials())});$('cvat-frame').replaceChildren();for(const frame of result.frames){if(!/\.(pcd|bin)$/i.test(frame.name))continue;const option=document.createElement('option');option.value=frame.id;option.textContent=`${frame.id} · ${frame.name}`;$('cvat-frame').append(option)}message(`Đã tìm thấy ${$('cvat-frame').options.length} point cloud frame.`)}catch(error){fail(error)}};
$('btn-import').onclick=async()=>{try{const result=await api('/api/sessions/cvat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...credentials(),frame:Number($('cvat-frame').value)})});await openSession(result.id);message(result.import_warnings?.length?result.import_warnings.join(' · '):`Đã mở frame CVAT: ${result.labels.length} nhãn, ${result.boxes.length} box.`,!!result.import_warnings?.length) }catch(error){fail(error)}};
$('btn-detect').onclick=async()=>{
  if(!state.session||state.detecting)return;
  if(state.saving){message('Chờ lưu box hiện tại xong trước khi chạy model.',true);return}
  const sessionId=state.session.id,modelId=$('model').value,mode=$('detect-mode').value;
  if(mode==='replace'&&state.session.boxes.length&&!confirm(`Ghi đè toàn bộ ${state.session.boxes.length} object hiện tại bằng kết quả model mới? Box cũ sẽ chuyển vào “Box đã xoá” và có thể khôi phục. Nếu model không tìm thấy object, danh sách hiện tại sẽ trống.`))return;
  try{
    state.detecting=true;setDetectorBusy(true);updateDetectorHelp();message('Model đang xử lý point cloud; lần đầu cần thời gian nạp checkpoint…');
    const result=await api(`/api/sessions/${sessionId}/detect`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:state.session.revision,model_id:modelId,mode,threshold:Number($('threshold').value),label_map:currentMapping(),class_thresholds:$('detect-profile').value==='custom'?currentClassThresholds():{},profile:$('detect-profile').value})});
    if(state.session.id!==sessionId)return;
    await openSession(sessionId);
    const info=result.detection;
    message(`${info.mode==='replace'?`Đã thay ${info.replaced} object cũ bằng ${info.added} box nháp mới. Box cũ có thể khôi phục trong “Box đã xoá”.`:`Thêm ${info.added} box nháp. Các box cũ được giữ lại.`} Bỏ qua ${info.duplicates_skipped} box trùng và ${info.classes_skipped} box không ánh xạ/bỏ qua, ${info.below_threshold} box dưới ngưỡng lớp. Hãy kiểm tra trước khi chấp nhận.`);
  }catch(error){fail(error)}finally{state.detecting=false;setDetectorBusy(false);updateDetectorHelp()}
};
$('btn-add').onclick=()=>addBoxAt(state.viewTarget||state.bounds.mid);
$('projection-focus').onchange=()=>{state.projectionFocus=$('projection-focus').checked;state.zoom=1;$('projection-hint').textContent=state.projectionFocus?'Chỉ vùng quanh box đang chọn':'Toàn cảnh hình chiếu';render()};
$('btn-delete-box').onclick=()=>archiveSelected();
for(const name of ['center-x','center-y','center-z','size-x','size-y','size-z','yaw','pitch','roll'])$(name).onchange=async()=>{const box=selected();if(!box)return;const value=Number($(name).value);if(!Number.isFinite(value)||(name.startsWith('size')&&value<=0)){message('Giá trị phải hữu hạn; kích thước phải lớn hơn 0.',true);populateEditor();return}if(['yaw','pitch','roll'].includes(name))box[name]=value*Math.PI/180;else{const [group,axis]=name.split('-');box[group==='center'?'center':'size']['xyz'.indexOf(axis)]=value}render();await save()};
$('edit-label').onchange=async()=>{const box=selected();if(box){box.label=$('edit-label').value;render();await save()}};
document.querySelectorAll('[data-flip]').forEach(button=>button.onclick=async()=>{const box=selected();if(!box)return;const axis=Number(button.dataset.flip);box.axis_signs[axis]*=-1;populateEditor();render();await save()});
$('box-axis-order').onchange=async()=>{const box=selected();if(!box)return;box.axis_order=$('box-axis-order').value.split(',').map(Number);populateEditor();render();await save()};
document.querySelectorAll('[data-swap]').forEach(button=>button.onclick=async()=>{const box=selected();if(!box)return;const [a,b]=button.dataset.swap.split(',').map(Number);box.axis_order??=[0,1,2];[box.axis_order[a],box.axis_order[b]]=[box.axis_order[b],box.axis_order[a]];[box.axis_signs[a],box.axis_signs[b]]=[box.axis_signs[b],box.axis_signs[a]];populateEditor();render();await save()});
$('btn-session-axes').onclick=()=>saveAxisConvention(false);$('btn-apply-axes').onclick=()=>saveAxisConvention(true);
$('btn-accept').onclick=()=>reviewBoxes('accepted');
$('btn-reject').onclick=()=>reviewBoxes('rejected');
$('btn-pending').onclick=()=>reviewBoxes('pending');
$('btn-accept-all').onclick=()=>reviewBoxes('accepted',true);
$('btn-export').onclick=()=>{const blob=new Blob([JSON.stringify({version:3,coordinate_system:'LiDAR XYZ metres, Z up',...state.session,points:undefined},null,2)],{type:'application/json'});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download=`v3-${state.session.id}.json`;link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000)};
$('file-import').onchange=async event=>{const file=event.target.files[0];if(!file||!state.session)return;try{const text=await file.text();const data=JSON.parse(text);if(data.boxes){state.session.boxes=data.boxes;renderList();render();await save();message('Đã nạp bản backup JSON.')}}catch(error){fail(error)}};
$('btn-publish').onclick=async()=>{
  if(!state.session?.cvat)return;
  if(state.saving||state.detecting||state.drag){message('Chờ lưu/chạy model xong trước khi publish.',true);return}
  const count=state.session.boxes.filter(box=>box.status==='accepted').length;
  if(!count){message('Chưa có box nào được chấp nhận.',true);return}
  let payload;
  try{payload=CVATClient.publishPayload(state.session.cvat,credentials())}catch(error){const details=$('cvat-user').closest('details');if(details)details.open=true;$('cvat-user').focus();fail(error);return}
  payload.mode=$('detect-mode').value;payload.revision=state.session.revision;
  const sessionId=state.session.id;state.saving=true;setDetectorBusy(true);$('btn-publish').disabled=true;$('save-state').textContent='Đang chuẩn bị publish…';
  try{
    if(payload.mode==='replace'){
      const preview=await api(`/api/sessions/${sessionId}/publish-preview`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      if(state.session.id!==sessionId)return;
      const targets=preview.targets.map(item=>`ID ${item.id} · label ${item.label_id} · ${item.type}`).join('\n')||'(Không có annotation cũ)';
      if(!confirm(`GHI ĐÈ CVAT job ${payload.job_id}, frame ${preview.frame}\nThay ${preview.targets.length} annotation sau bằng ${count} box đã chấp nhận:\n${targets}\n\nBản sao đầy đủ được lưu trên máy trước khi thay. CVAT không có nút hoàn tác đảm bảo cho thao tác này. Xác nhận ghi đè?`)){$('save-state').textContent=`Đã lưu · r${state.session.revision}`;return}
      payload.replacement_token=preview.replacement_token;payload.revision=preview.revision;
    }else if(!confirm(`THÊM box mới đã chấp nhận vào CVAT job ${payload.job_id}, frame ${state.session.cvat.frame}? Annotation cũ được giữ lại.`)){$('save-state').textContent=`Đã lưu · r${state.session.revision}`;return}
    $('save-state').textContent='Đang publish…';
    const result=await api(`/api/sessions/${sessionId}/publish`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    if(state.session.id!==sessionId)return;
    state.session.revision=result.revision??state.session.revision;$('save-state').textContent=`Đã lưu · r${state.session.revision}`;message(result.published?(result.mode==='replace'?`Đã thay ${result.replaced} annotation cũ bằng ${result.published} box trên CVAT.`:`Đã thêm ${result.published} box lên CVAT.`):'Không có box đã chấp nhận mới để publish.');
  }catch(error){$('save-state').textContent='Publish lỗi';fail(error)}finally{state.saving=false;setDetectorBusy(false);$('btn-publish').disabled=!state.session?.cvat}
};
$('camera-files').onchange=async event=>{if(!state.session){message('Mở point cloud trước khi thêm camera.',true);return}for(const file of event.target.files){try{const result=await api(`/api/sessions/${state.session.id}/cameras?filename=${encodeURIComponent(file.name)}`,{method:'POST',headers:{'Content-Type':file.type||'application/octet-stream'},body:file});state.session={...state.session,...result};renderCameras();$('save-state').textContent=`Đã lưu · r${result.revision}`}catch(error){fail(error);break}}};
initAxisControls();loadModels();const existing=new URLSearchParams(location.search).get('session') || localStorage.getItem('cvat-v4-last-session');if(existing)openSession(existing).catch(fail);render();

function currentClassThresholds(){const values={};for(const input of $('label-mapping').querySelectorAll('[data-threshold-source]'))if(input.value.trim()!==''){const value=Number(input.value);if(!Number.isFinite(value)||value<0||value>1)throw new Error('Ngưỡng theo lớp phải từ 0 đến 1.');values[input.dataset.thresholdSource.toLowerCase()]=value}return values}
function renderDetectionReport(){
  const area=$('detection-report');area.replaceChildren();const info=state.session?.detection;if(!info){$('detect-summary').textContent='';return;}
  $('detect-summary').textContent=`Lần chạy gần nhất: thêm ${info.added} box · bỏ qua ${info.duplicates_skipped} trùng, ${info.classes_skipped} không ánh xạ.`;
  const summary=document.createElement('p');summary.textContent=`Lần chạy gần nhất: model trả ${info.returned??'—'} box · thêm ${info.added} · trùng ${info.duplicates_skipped} · dưới ngưỡng lớp ${info.below_threshold??0} · không ánh xạ/bỏ qua ${info.classes_skipped}`;area.append(summary);
  for(const [source,row] of Object.entries(info.by_class||{})){const line=document.createElement('p');line.textContent=`${source}: ${row.returned} trả về, ${row.mapped} qua lọc, ${row.below_threshold} dưới ngưỡng, ${row.explicit_skip+row.unmapped} bỏ qua`;area.append(line)}
  const note=document.createElement('p');note.textContent='Thống kê bắt đầu từ box model trả về sau lọc/NMS. Không đếm được vật thể model chưa phát hiện; nuScenes Mac có ngưỡng sàn 0,05 (PointPillars) hoặc 0,10 (CenterPoint).';area.append(note);
}
function setPointSize(value){
  const levels=[.5,1,1.5,2,3,4,6];
  state.pointSize=levels.reduce((best,level)=>Math.abs(level-value)<Math.abs(best-value)?level:best,1.5);
  $('point-size-value').textContent=`${state.pointSize.toLocaleString('vi-VN')} px`;
  document.querySelectorAll('[data-point-size]').forEach(button=>button.setAttribute('aria-pressed',String(Number(button.dataset.pointSize)===state.pointSize)));
  localStorage.setItem('cvat-point-size',String(state.pointSize));render();
}
document.querySelectorAll('[data-point-size]').forEach(button=>button.onclick=()=>setPointSize(Number(button.dataset.pointSize)));
$('point-size-reset').onclick=()=>setPointSize(1.5);setPointSize(state.pointSize);

state.pointColorMode=localStorage.getItem('cvat-point-color-mode')==='uniform'?'uniform':'source';
$('point-color-mode').value=state.pointColorMode;
$('point-color-mode').onchange=()=>{state.pointColorMode=$('point-color-mode').value;localStorage.setItem('cvat-point-color-mode',state.pointColorMode);render()};

function detectorPreferenceKey(){return 'cvat-detect-preferences:'+JSON.stringify(state.session?.cvat?[state.session.cvat.url,state.session.cvat.job_id]:state.session?.labels||[])}
function readDetectorPreferences(){try{return JSON.parse(localStorage.getItem(detectorPreferenceKey())||'{}')}catch{return {}}}
function saveDetectorPreferences(){if(!state.session)return;localStorage.setItem(detectorPreferenceKey(),JSON.stringify({model_id:$('model').value,profile:$('detect-profile').value,threshold:Number($('threshold').value),mapping:currentMapping()}))}
function restoreDetectorPreferences(){const preferences=readDetectorPreferences();if([...$('model').options].some(option=>option.value===preferences.model_id))$('model').value=preferences.model_id;$('detect-profile').value=['precise','balanced','recall','custom'].includes(preferences.profile)?preferences.profile:'balanced';if(Number.isFinite(preferences.threshold))$('threshold').value=preferences.threshold;updateProfileUI()}
function updateProfileUI(){const profile=$('detect-profile').value;const thresholds={precise:.55,balanced:.3,recall:.15};if(profile!=='custom')$('threshold').value=thresholds[profile];$('profile-hint').textContent={precise:'Ngưỡng cao: ít đề xuất yếu; có thể bỏ sót thêm vật thể.',balanced:'Ngưỡng trung bình để bắt đầu; chưa phải cấu hình tối ưu cho bài.',recall:'Ngưỡng thấp: thêm đề xuất; thường cần từ chối nhiều box sai hơn.',custom:'Dùng ngưỡng chung và theo lớp trong Nâng cao.'}[profile];}
$('detect-profile').onchange=()=>{updateProfileUI();saveDetectorPreferences()};$('threshold').onchange=()=>{$('detect-profile').value='custom';updateProfileUI();saveDetectorPreferences()};
$('btn-evaluation-frames').onclick=async()=>{if(!state.session)return;try{const result=await api(`/api/sessions/${state.session.id}/evaluation-candidates`);const area=$('evaluation-frames');area.replaceChildren();for(const frame of result.candidates){const label=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.value=frame.id;input.checked=frame.id===state.session.id;label.append(input,document.createTextNode(` ${frame.frame==null?frame.title:'Frame '+frame.frame} · ${frame.accepted} box`));area.append(label)}$('evaluation-status').textContent=result.candidates.length?'Chọn frame đã kiểm tra đầy đủ.':'Chưa có frame chứa box chấp nhận.'}catch(error){fail(error)}};
$('btn-evaluate').onclick=async()=>{
 if(!state.session||state.detecting||state.saving)return;
 const sessionId=state.session.id,ids=[...$('evaluation-frames').querySelectorAll('input:checked')].map(input=>input.value);
 if(!ids.length||ids.length>20||!$('evaluation-complete').checked){message('Chọn 1–20 frame và xác nhận đã gắn đủ vật thể.',true);return;}
 state.detecting=true;setDetectorBusy(true);updateDetectorHelp();$('btn-evaluate').disabled=true;$('evaluation-status').textContent='Đang chạy hai model trên frame mẫu… Có thể mất vài phút; box trong bài được giữ nguyên.';
 try{const result=await api(`/api/sessions/${sessionId}/evaluate`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:state.session.revision,session_ids:ids,confirmed_complete:true,label_map:currentMapping()})});if(state.session.id!==sessionId)return;state.evaluation=result;renderEvaluation(result)}catch(error){$('evaluation-status').textContent=error.message;fail(error)}finally{state.detecting=false;setDetectorBusy(false);$('btn-evaluate').disabled=false;updateDetectorHelp()}
};
function renderEvaluation(report){
 const area=$('evaluation-results');area.replaceChildren();const table=document.createElement('table');const heading=document.createElement('tr');for(const name of ['Model / chế độ','Đúng','Thừa','Thiếu','P / R','Lệch tâm']){const th=document.createElement('th');th.textContent=name;heading.append(th)}table.append(heading);
 for(const row of report.results){const tr=document.createElement('tr');for(const value of [row.model_id.replace('-nuscenes','')+' / '+({precise:'Ít sai',balanced:'Cân bằng',recall:'Tìm thêm'}[row.profile]),row.tp,row.fp,row.fn,`${(row.precision*100).toFixed(0)}% / ${(row.recall*100).toFixed(0)}%`,row.center_error_m==null?'—':row.center_error_m.toFixed(2)+' m']){const td=document.createElement('td');td.textContent=String(value);tr.append(td)}table.append(tr)}area.append(table);
 const detail=document.createElement('details'),summary=document.createElement('summary');summary.textContent='Theo nhãn · cấu hình đề xuất';detail.append(summary);for(const [label,row] of Object.entries(report.recommendation?.by_label||{})){const line=document.createElement('p');line.textContent=`${label}: ${row.tp} đúng · ${row.fp} thừa · ${row.fn} thiếu · lệch kích thước ${row.size_error_m==null?'—':row.size_error_m.toFixed(2)+' m'}`;detail.append(line)}area.append(detail);
 $('evaluation-status').textContent=`${report.samples.length} frame. ${report.metric} P=precision, R=recall. ${report.recommendation?'Đề xuất theo F1 trên các frame mẫu; cần kiểm tra trên frame khác.':'Chưa có dự đoán đúng để đề xuất.'}`;$('btn-apply-recommendation').hidden=!report.recommendation;
}
$('btn-apply-recommendation').onclick=()=>{const best=state.evaluation?.recommendation;if(!best)return;$('model').value=best.model_id;$('detect-profile').value=best.profile;renderMapping();updateProfileUI();saveDetectorPreferences();message('Đã lưu cấu hình đề xuất cho bài. Bấm Auto detect để dùng trên frame mới.')};
$('btn-input-check').onclick=async()=>{if(!state.session)return;try{const report=await api(`/api/sessions/${state.session.id}/input-diagnostics`);$('input-diagnostics').textContent=report.summary}catch(error){fail(error)}};

function showAccessModal(force = false) {
  const modal = $('access-modal');
  if (!modal) return;
  const lastActive = parseInt(localStorage.getItem('v4_access_time') || '0', 10);
  const now = Date.now();
  const SEVEN_DAYS = 7 * 24 * 60 * 60 * 1000;
  if (force || !localStorage.getItem('v4_access_key') || (now - lastActive > SEVEN_DAYS)) {
    modal.style.display = 'flex';
  } else {
    localStorage.setItem('v4_access_time', String(now));
  }
}
window.showAccessModal = showAccessModal;

$('btn-submit-key')?.addEventListener('click', async () => {
  const input = $('access-key-input').value.trim();
  if (!input) return;
  localStorage.setItem('v4_access_key', input);
  try {
    await api('/api/models'); // Test key
    localStorage.setItem('v4_access_time', String(Date.now()));
    $('access-modal').style.display = 'none';
    $('access-error').style.display = 'none';
    window.location.reload();
  } catch (error) {
    if (error.message.includes('401')) {
      $('access-error').style.display = 'block';
      localStorage.removeItem('v4_access_key');
    }
  }
});

// CVAT Auto Fetch Logic
function initCVAT() {
  const savedUrl = localStorage.getItem('v4_cvat_url');
  const savedUser = localStorage.getItem('v4_cvat_user');
  const savedPass = localStorage.getItem('v4_cvat_pass');
  if (savedUrl && savedUser && savedPass) {
    $('cvat-url').value = savedUrl;
    $('cvat-user').value = savedUser;
    $('cvat-pass').value = savedPass;
    $('cvat-login-form').style.display = 'none';
    $('cvat-job-section').style.display = 'block';
    $('cvat-current-user').textContent = savedUser;
    fetchCVATJobs();
  } else {
    $('cvat-login-form').style.display = 'block';
    $('cvat-job-section').style.display = 'none';
  }
}
async function fetchCVATJobs() {
  const btn = $('btn-fetch-jobs');
  btn.disabled = true;
  btn.textContent = 'Đang tải...';
  try {
    const data = await api('/api/cvat/jobs', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(credentials())
    });
    localStorage.setItem('v4_cvat_url', $('cvat-url').value);
    localStorage.setItem('v4_cvat_user', $('cvat-user').value);
    localStorage.setItem('v4_cvat_pass', $('cvat-pass').value);
    $('cvat-login-form').style.display = 'none';
    $('cvat-job-section').style.display = 'block';
    $('cvat-current-user').textContent = $('cvat-user').value;
    
    const select = $('cvat-job-select');
    select.replaceChildren();
    for (const job of data.jobs) {
      const option = document.createElement('option');
      option.value = job.id;
      option.textContent = `T${job.task_id} · Job ${job.id} (${job.stage})`;
      select.append(option);
    }
    select.onchange = () => { $('cvat-job').value = select.value; };
    if (data.jobs.length > 0) {
      select.value = data.jobs[0].id;
      $('cvat-job').value = data.jobs[0].id;
    }
    message(`Đã tải ${data.jobs.length} Job từ CVAT.`);
  } catch (error) {
    if (error.message.includes('Unable to log in') || error.message.includes('400')) {
      $('btn-cvat-logout').click(); // Auto clear bad credentials and show form
      fail('Sai tài khoản hoặc mật khẩu CVAT! Vui lòng nhập lại.');
    } else {
      fail(error);
    }
  } finally {
    btn.disabled = false;
    btn.textContent = 'Kết nối & Tải danh sách Job';
  }
}
$('btn-fetch-jobs')?.addEventListener('click', fetchCVATJobs);
$('btn-cvat-logout')?.addEventListener('click', () => {
  localStorage.removeItem('v4_cvat_url');
  localStorage.removeItem('v4_cvat_user');
  localStorage.removeItem('v4_cvat_pass');
  $('cvat-login-form').style.display = 'block';
  $('cvat-job-section').style.display = 'none';
  $('cvat-url').value = '';
  $('cvat-user').value = '';
  $('cvat-pass').value = '';
});

// Init on load
document.addEventListener('DOMContentLoaded', () => {
  showAccessModal();
  initCVAT();
});
