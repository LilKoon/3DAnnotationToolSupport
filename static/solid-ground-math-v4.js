/* Geometry shared by WebGL rendering and depth-aware picking. No dataset mutation. */
(function(root){
 const dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0);
 function height(record,p){const s=record?.cell_size;if(!s)return null;const c=record.cells.find(c=>c[0]===Math.floor(p[0]/s)&&c[1]===Math.floor(p[1]/s));return c?c[2]*p[0]+c[3]*p[1]+c[4]:null;}
 function clampElevation(e,allowBelow){return Math.max(allowBelow?-1.4:.06,Math.min(1.4,e));}
 function mesh(record,style='data',fill=true){
  if(!record)return {triangles:[],filled:0,reference:false};
  const size=record.cell_size,cells=record.cells||[],triangles=[...(record.surface||[])];
  if(style==='reference'&&cells.length){
   const xs=cells.map(c=>c[0]*size),ys=cells.map(c=>c[1]*size),zs=cells.map(c=>c[2]*(c[0]+.5)*size+c[3]*(c[1]+.5)*size+c[4]).sort((a,b)=>a-b);
   const z=zs[Math.floor(zs.length/2)],x0=Math.min(...xs),x1=Math.max(...xs)+size,y0=Math.min(...ys),y1=Math.max(...ys)+size;
   return {triangles:[[[x0,y0,z],[x1,y0,z],[x1,y1,z]],[[x0,y0,z],[x1,y1,z],[x0,y1,z]]],filled:0,reference:true};
  }
  let filled=0;
  if(fill){
   const map=new Map(cells.map(c=>[c[0]+','+c[1],c])),candidates=new Set();
   for(const c of cells)for(const [dx,dy] of [[1,0],[-1,0],[0,1],[0,-1]]){const k=(c[0]+dx)+','+(c[1]+dy);if(!map.has(k))candidates.add(k);}
   for(const key of candidates){
    if(triangles.length>=6000)break;
    const [x,y]=key.split(',').map(Number),neighbors=[[1,0],[-1,0],[0,1],[0,-1]].map(([dx,dy])=>map.get((x+dx)+','+(y+dy)));if(neighbors.some(c=>!c))continue;
    const heights=neighbors.map(c=>c[2]*(x+.5)*size+c[3]*(y+.5)*size+c[4]);
    if(Math.max(...heights)-Math.min(...heights)>.15)continue;
    const vertices=[[0,0],[1,0],[1,1],[0,1]].map(([dx,dy])=>{const px=(x+dx)*size,py=(y+dy)*size;return [px,py,neighbors.reduce((s,c)=>s+c[2]*px+c[3]*py+c[4],0)/4];});
    // Do not bridge steep/discontinuous corner heights either.
    if(vertices.some(p=>{const h=neighbors.map(c=>c[2]*p[0]+c[3]*p[1]+c[4]);return Math.max(...h)-Math.min(...h)>.15;}))continue;
    triangles.push([vertices[0],vertices[1],vertices[2]],[vertices[0],vertices[2],vertices[3]]);filled++;
   }
  }
  return {triangles,filled,reference:false};
 }
 function surfaceDepth(triangles,p){
  let depth=Infinity;
  for(const [a,b,c] of triangles){
   const d=(b.y-c.y)*(a.x-c.x)+(c.x-b.x)*(a.y-c.y);if(Math.abs(d)<1e-8)continue;
   const u=((b.y-c.y)*(p.x-c.x)+(c.x-b.x)*(p.y-c.y))/d,v=((c.y-a.y)*(p.x-c.x)+(a.x-c.x)*(p.y-c.y))/d,w=1-u-v;
   if(u>=-1e-6&&v>=-1e-6&&w>=-1e-6)depth=Math.min(depth,u*a.depth+v*b.depth+w*c.depth);
  }
  return depth;
 }
 function visibleAt(triangles,p,xray){return xray||p.depth<=surfaceDepth(triangles,p)+.025;}
 function rayBox(origin,direction,box){
  const a=box.roll||0,b=box.pitch||0,c=box.yaw||0,ca=Math.cos(a),sa=Math.sin(a),cb=Math.cos(b),sb=Math.sin(b),cc=Math.cos(c),sc=Math.sin(c);
  const axes=[[cc*cb,sc*cb,-sb],[cc*sb*sa-sc*ca,sc*sb*sa+cc*ca,cb*sa],[cc*sb*ca+sc*sa,sc*sb*ca-cc*sa,cb*ca]];
  const delta=origin.map((v,i)=>v-box.center[i]);let low=0,high=Infinity;
  for(let i=0;i<3;i++){const o=dot(delta,axes[i]),d=dot(direction,axes[i]),half=box.size[i]/2;if(Math.abs(d)<1e-9){if(Math.abs(o)>half)return null;continue;}const t0=(-half-o)/d,t1=(half-o)/d;low=Math.max(low,Math.min(t0,t1));high=Math.min(high,Math.max(t0,t1));if(high<low)return null;}return low;
 }
 const api={height,clampElevation,mesh,surfaceDepth,visibleAt,rayBox};root.SolidGroundMath=api;if(typeof module!=='undefined')module.exports=api;
})(globalThis);

(function(){
 const indexes=new WeakMap();
 SolidGroundMath.height=function(record,p){
  if(!record?.cell_size)return null;
  let map=indexes.get(record);if(!map){map=new Map((record.cells||[]).map(c=>[c[0]+','+c[1],c]));indexes.set(record,map);}
  const c=map.get(Math.floor(p[0]/record.cell_size)+','+Math.floor(p[1]/record.cell_size));
  return c?c[2]*p[0]+c[3]*p[1]+c[4]:null;
 };
})();

(function(){
 const cache=new WeakMap();
 SolidGroundMath.referenceHeight=function(record){
  if(!record?.cell_size||!record.cells?.length)return null;
  if(cache.has(record))return cache.get(record);
  const size=record.cell_size,z=record.cells.map(c=>c[2]*(c[0]+.5)*size+c[3]*(c[1]+.5)*size+c[4]).sort((a,b)=>a-b);
  const result=z[Math.floor(z.length/2)];cache.set(record,result);return result;
 };
 SolidGroundMath.sideVisible=function(record,p,elevation,options){
  if(options.floorOnly&&!options.xray&&elevation<0&&SolidGroundMath.referenceHeight(record)!==null)return false;
  if(!options.seal||options.xray)return true;
  if(elevation<0&&options.floorOnly&&SolidGroundMath.referenceHeight(record)!==null)return false;
  const reference=SolidGroundMath.referenceHeight(record);if(reference===null)return true;
  const local=options.style==='reference'?null:SolidGroundMath.height(record,p);
  return (p[2]-(local??reference))*(elevation<0?-1:1)>=-.025;
 };
})();
