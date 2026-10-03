(function(root){
  const defaults={mode:'raw',focus:false,maxRange:100,zMin:null,zMax:null,margin:1};
  function visible(p,i,kind,state){
    const options=state.v4Scene||defaults;
    if(Math.hypot(p[0],p[1])>options.maxRange)return false;
    if(options.zMin!==null&&p[2]<options.zMin||options.zMax!==null&&p[2]>options.zMax)return false;
    if(['hide','surface'].includes(options.mode)&&state.v4Ground?.display_mask?.[i]===1)return false;
    if(options.focus&&kind==='main'){
      const box=state.session?.boxes.find(b=>b.id===state.selected);
      if(box){const x=p[0]-box.center[0],y=p[1]-box.center[1],c=Math.cos(box.yaw),s=Math.sin(box.yaw),m=options.margin??1;
        if(Math.abs(x*c+y*s)>box.size[0]/2+m||Math.abs(-x*s+y*c)>box.size[1]/2+m||Math.abs(p[2]-box.center[2])>box.size[2]/2+m)return false;}
    }
    return true;
  }
  function alpha(i,state){return state.v4Scene?.mode==='dim'&&state.v4Ground?.display_mask?.[i]===1?.12:1;}
  function drawSurface(g,kind,state){
    if(kind!=='main'||state.v4Scene?.mode!=='surface'||!state.v4Ground)return;
    const tiles=state.v4Ground.surface.filter(t=>t.some(p=>visible(p,-1,kind,state))).map(t=>t.map(g.project)).sort((a,b)=>b.reduce((s,p)=>s+p.depth,0)-a.reduce((s,p)=>s+p.depth,0));
    g.ctx.fillStyle='#263b47';g.ctx.strokeStyle='#314955';g.ctx.lineWidth=.5;
    for(const t of tiles){g.ctx.beginPath();t.forEach((p,i)=>i?g.ctx.lineTo(p.x,p.y):g.ctx.moveTo(p.x,p.y));g.ctx.closePath();g.ctx.fill();g.ctx.stroke();}
  }
  const api={defaults,visible,alpha,drawSurface};root.V4Scene=api;if(typeof module!=='undefined')module.exports=api;
})(globalThis);

// Extend focus to full cuboid orientation while keeping the public scene API.
(function(){
  const base=V4Scene.visible;V4Scene.defaults.maxRange=Infinity;
  V4Scene.visible=function(p,i,kind,state){
    const options=state.v4Scene||V4Scene.defaults;
    if(!options.focus||kind!=='main')return base(p,i,kind,state);
    const box=state.session?.boxes.find(b=>b.id===state.selected);
    if(!box)return base(p,i,kind,state);
    const pass=base(p,i,kind,{...state,v4Scene:{...options,focus:false}});if(!pass)return false;
    const a=box.roll||0,b=box.pitch||0,c=box.yaw||0,ca=Math.cos(a),sa=Math.sin(a),cb=Math.cos(b),sb=Math.sin(b),cc=Math.cos(c),sc=Math.sin(c);
    const axes=[[cc*cb,sc*cb,-sb],[cc*sb*sa-sc*ca,sc*sb*sa+cc*ca,cb*sa],[cc*sb*ca+sc*sa,sc*sb*ca-cc*sa,cb*ca]],delta=p.slice(0,3).map((v,j)=>v-box.center[j]);
    return axes.every((axis,j)=>Math.abs(axis.reduce((s,v,k)=>s+v*delta[k],0))<=box.size[j]/2+(options.margin??1));
  };
})();
