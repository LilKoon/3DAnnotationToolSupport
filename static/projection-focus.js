(function(root){
  function nearBox(point,box,kind){
    const editor=typeof CuboidEdit!=='undefined'?CuboidEdit:require('./cuboid-edit.js'),delta=point.slice(0,3).map((v,i)=>v-box.center[i]);
    const local=editor.basis(box).map(axis=>editor.dot(axis,delta));
    const depthAxis=kind==='top'?2:kind==='front'?1:0;
    return local.every((value,i)=>Math.abs(value)<=box.size[i]/2+(i===depthAxis?.6:2));
  }
  function fitScale(box,kind,width,height){
    const editor=typeof CuboidEdit!=='undefined'?CuboidEdit:require('./cuboid-edit.js'),axes=editor.basis(box),extent=[0,1,2].map(i=>axes.reduce((sum,axis,k)=>sum+Math.abs(axis[i])*box.size[k],0));
    const span=kind==='top'?[extent[0],extent[1]]:kind==='front'?[extent[0],extent[2]]:[extent[1],extent[2]];
    return Math.min(width*.65/Math.max(span[0],.2),height*.65/Math.max(span[1],.2));
  }
  function hull(points){
    const sorted=[...new Map(points.map(p=>[`${p.x},${p.y}`,p])).values()].sort((a,b)=>a.x-b.x||a.y-b.y);
    const cross=(a,b,c)=>(b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);
    const half=items=>{const out=[];for(const p of items){while(out.length>1&&cross(out[out.length-2],out[out.length-1],p)<=0)out.pop();out.push(p)}return out};
    if(sorted.length<3)return sorted;
    return [...half(sorted).slice(0,-1),...half([...sorted].reverse()).slice(0,-1)];
  }
  const api={nearBox,fitScale,hull};if(typeof module!=='undefined'&&module.exports)module.exports=api;root.ProjectionFocus=api;
})(typeof window!=='undefined'?window:globalThis);
