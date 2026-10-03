/* Dock original controls without replacing their IDs, state or handlers. */
(function(){
 const layout=document.querySelector('.layout'),left=document.querySelector('.left-panel'),right=document.querySelector('.right-panel'),workspace=document.querySelector('.workspace');
 if(!layout||layout.classList.contains('v4-dock'))return;
 let saved=null;try{saved=JSON.parse(localStorage.getItem('v4-workspace-layout'));}catch{}
 let preferences=WorkspaceLayoutModel.normalize(saved,window.innerWidth),focusBackup=null;
 const pages={},rails={},bodies={},headings={},toggles={};
 const definitions={left:[['data','Dữ liệu','File, CVAT và hệ trục'],['ai','AI','Model và tự động nhận diện'],['display','Hiển thị','Điểm LiDAR, mặt đất và góc nhìn']],right:[['objects','Objects','Danh sách, duyệt và chỉnh cuboid'],['camera','Camera','Ảnh tham chiếu và đối chiếu'],['quality','Kiểm tra','Chất lượng và nhãn chuẩn']]};
 const icons={data:'M4 5h16v14H4z M4 9h16 M8 5v14',ai:'M6 6h12v12H6z M9 2v4 M15 2v4 M9 18v4 M15 18v4 M2 9h4 M2 15h4 M18 9h4 M18 15h4',display:'M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7z M9 12a3 3 0 1 0 6 0a3 3 0 1 0-6 0',objects:'M4 7l8-4 8 4v10l-8 4-8-4z M4 7l8 4 8-4 M12 11v10',camera:'M3 7h5l2-3h4l2 3h5v13H3z M8 13a4 4 0 1 0 8 0a4 4 0 1 0-8 0',quality:'M4 3h16v18H4z M8 12l3 3 6-7'};
 function button(text,id,action){const node=document.createElement('button');node.type='button';node.textContent=text;if(id)node.id=id;node.onclick=action;return node;}
 function resize(){requestAnimationFrame(()=>render());}
 function apply(persist=true){
  if(preferences.left&&!WorkspaceLayoutModel.pages.left.includes(preferences.leftPage))preferences.leftPage='data';
  layout.classList.toggle('v4-left-open',preferences.left);layout.classList.toggle('v4-right-open',preferences.right);
  for(const side of ['left','right']){
   const panel=side==='left'?left:right;panel.hidden=!preferences[side];
   const active=preferences[side+'Page'];
   for(const [key,title,hint] of definitions[side]){
    pages[key].hidden=key!==active;
    toggles[key].setAttribute('aria-expanded',String(preferences[side]&&active===key));
    toggles[key].classList.toggle('v4-rail-active',preferences[side]&&active===key);
    if(key===active){headings[side].querySelector('strong').textContent=title;headings[side].querySelector('small').textContent=hint;}
   }
  }
  document.querySelector('.projection-grid').hidden=!preferences.projections;
  document.querySelector('.projection-options').hidden=!preferences.projections;
  projectionToggle.setAttribute('aria-pressed',String(preferences.projections));
  focusToggle.setAttribute('aria-pressed',String(!!focusBackup));
  focusToggle.textContent=focusBackup?'Thoát tập trung':'Tập trung';
  if(persist)try{localStorage.setItem('v4-workspace-layout',focusBackup&&JSON.stringify(focusBackup)||JSON.stringify(preferences));}catch{}
  resize();
 }
 function open(side,key){if(focusBackup){preferences={...focusBackup};focusBackup=null;}preferences=WorkspaceLayoutModel.open(preferences,side,key,window.innerWidth);apply();}
 for(const side of ['left','right']){
  const panel=side==='left'?left:right,rail=document.createElement('nav');rail.className='v4-edge-rail v4-edge-'+side;rail.setAttribute('aria-label',side==='left'?'Công cụ dữ liệu và hiển thị':'Công cụ object và kiểm tra');rails[side]=rail;
  if(side==='left')layout.prepend(rail);else layout.append(rail);
  const heading=document.createElement('div');heading.className='v4-dock-heading';
  const title=document.createElement('div');title.innerHTML='<strong></strong><small></small>';heading.append(title,button(side==='left'?'‹':'›','v4-collapse-'+side,()=>{preferences[side]=false;apply();toggles[preferences[side+'Page']].focus();}));
  heading.lastChild.setAttribute('aria-label',side==='left'?'Thu gọn thanh trái':'Thu gọn thanh phải');
  headings[side]=heading;const body=document.createElement('div');body.className='v4-dock-body';bodies[side]=body;
  panel.prepend(heading,body);panel.id='v4-dock-'+side;
  for(const [key,name] of definitions[side]){
   const page=document.createElement('div');page.className='v4-dock-page';page.id='v4-page-'+key;pages[key]=page;body.append(page);
   const toggle=button('', 'v4-tab-'+key,()=>open(side,key));toggle.title=name;toggle.setAttribute('aria-label','Mở nhóm '+name);toggle.setAttribute('aria-controls',page.id);
   toggle.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="'+icons[key]+'"/></svg><span>'+name+'</span>';toggle.querySelector('span').textContent=key==='objects'?'Box':key==='camera'?'Ảnh':name;toggles[key]=toggle;rail.append(toggle);
  }
 }
 layout.classList.add('v4-dock');
 const actions=workspace.querySelector('.view-actions');
 const focusToggle=button('Tập trung','v4-focus-layout',()=>{
  if(focusBackup){preferences={...focusBackup};focusBackup=null;}
  else{focusBackup={...preferences};preferences={...preferences,left:false,right:false,projections:false};}
  apply();
 });
 focusToggle.title='Ẩn hai sidebar và hình chiếu · Shift + \\';
 const projectionToggle=button('Hình chiếu','v4-toggle-projections',()=>{
  preferences.projections=!preferences.projections;if(focusBackup)focusBackup.projections=preferences.projections;apply();
 });
 actions.prepend(focusToggle,projectionToggle);
 const originalSelect=select;
 select=function(id){
  originalSelect(id);
  if(id&&!focusBackup){preferences.right=true;preferences.rightPage='objects';if(window.innerWidth<1200)preferences.left=false;apply();}
 };
 const originalResize=resize;
 function refreshCamera(){originalResize();if(preferences.right&&preferences.rightPage==='camera')requestAnimationFrame(()=>globalThis.V4Camera?.selectionChanged());}
 for(const key of WorkspaceLayoutModel.pages.right)toggles[key].addEventListener('click',refreshCamera);
 window.addEventListener('resize',refreshCamera);
 function moveCard(node,key){if(node&&node.parentElement!==pages[key])pages[key].append(node);}
 function sourceCard(id){return document.getElementById(id)?.closest('section.card');}
 function route(){
  moveCard(sourceCard('file'),'data');moveCard(sourceCard('session-axis-order'),'data');
  moveCard(sourceCard('btn-detect'),'ai');moveCard(sourceCard('v4-ground-run'),'display');
  moveCard(sourceCard('objects'),'objects');moveCard(sourceCard('btn-accept-all'),'objects');moveCard(sourceCard('editor'),'objects');moveCard(sourceCard('v4-measure-run'),'objects');
  moveCard(sourceCard('camera-files'),'camera');moveCard(sourceCard('v4-image-run'),'camera');moveCard(sourceCard('v4-quality-run'),'quality');
  for(const selector of ['.point-size-toolbar','.v4-toolbar','.v4-solid-controls']){
   const node=document.querySelector(selector);if(node&&node.parentElement!==pages.display){node.classList.add('v4-display-block');pages.display.append(node);}
  }
  const help=document.querySelector('.navigation-help'),legend=document.querySelector('.legend');
  if(help&&help.parentElement===workspace){
   const details=document.createElement('details');details.className='card v4-shortcuts';const summary=document.createElement('summary');summary.textContent='Điều khiển & phím tắt';details.append(summary,help);if(legend)details.append(legend);pages.display.append(details);
  }
  const ordered=[document.querySelector('.point-size-toolbar'),viewCard,document.querySelector('.v4-toolbar'),document.querySelector('.v4-solid-controls'),sourceCard('v4-ground-run'),pages.display.querySelector('.v4-shortcuts')].filter(Boolean);
  ordered.forEach((node,index)=>{if(pages.display.children[index]!==node)pages.display.insertBefore(node,pages.display.children[index]||null);});
  const ground=document.querySelector('.v4-solid-controls');if(ground&&!ground.dataset.docked){ground.open=true;ground.open=false;ground.dataset.docked='true';}
 }
 const viewCard=document.createElement('section');viewCard.className='card v4-view-options';viewCard.innerHTML='<h2>Object & góc nhìn</h2>';
 pages.display.append(viewCard);
 for(const id of ['v4-solid-details','v4-solid-axes','v4-solid-below']){const input=document.getElementById(id);if(input)viewCard.append(input.parentElement);}
 for(const id of ['v4-solid-upright','v4-solid-xray','v4-solid-snapshot']){const control=document.getElementById(id);if(control)viewCard.append(control);}
 const audit=sourceCard('v4-ground-run');
 if(audit){
  const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent='Quét ground & kiểm tra dữ liệu';details.append(summary);
  for(const child of [...audit.children]){if(child.tagName==='H2')child.hidden=true;else details.append(child);}
  audit.append(details);
 }
 route();
 // V4 add-ons are independent async scripts; observe only their insertion sites.
 const observer=new MutationObserver(route);observer.observe(left,{childList:true});observer.observe(right,{childList:true});observer.observe(workspace,{childList:true});
 const resizeObserver=new ResizeObserver(resize);resizeObserver.observe(workspace);
 window.addEventListener('resize',()=>{if(window.innerWidth<1200&&preferences.left&&preferences.right)preferences.right=false;apply(false);});
 document.addEventListener('keydown',event=>{
  if(event.target.closest('input,select,textarea,[contenteditable="true"]'))return;
  if(event.shiftKey&&event.code==='Backslash'){event.preventDefault();focusToggle.click();}
  if(event.key==='Escape'&&window.innerWidth<901&&(preferences.left||preferences.right)){preferences.left=false;preferences.right=false;apply();views.main.focus();}
 });
 globalThis.V4Workspace={get preferences(){return {...preferences};},open};
 apply(false);
})();
