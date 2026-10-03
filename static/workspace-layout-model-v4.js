(function(root){
 const pages={left:['data','ai','display'],right:['objects','camera','quality']};
 function normalize(saved,width){
  const defaults={left:width>=1100,right:width>=1700,leftPage:'data',rightPage:'objects',projections:true};
  if(!saved||typeof saved!=='object')return defaults;
  for(const key of ['left','right','projections'])if(typeof saved[key]==='boolean')defaults[key]=saved[key];
  for(const side of ['left','right'])if(pages[side].includes(saved[side+'Page']))defaults[side+'Page']=saved[side+'Page'];
  if(width<1200&&defaults.left&&defaults.right)defaults.right=false;
  return defaults;
 }
 function open(current,side,page,width){
  if(!pages[side]?.includes(page))return {...current};
  const next={...current};next[side]=!current[side]||current[side+'Page']!==page;next[side+'Page']=page;
  if(next[side]&&width<1200)next[side==='left'?'right':'left']=false;
  return next;
 }
 const api={normalize,open,pages};root.WorkspaceLayoutModel=api;if(typeof module!=='undefined')module.exports=api;
})(globalThis);
