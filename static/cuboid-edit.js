(function(root){
  const dot=(a,b)=>a.reduce((sum,v,i)=>sum+v*b[i],0);
  function basis(box){
    const a=box.roll||0,b=box.pitch||0,c=box.yaw||0,ca=Math.cos(a),sa=Math.sin(a),cb=Math.cos(b),sb=Math.sin(b),cc=Math.cos(c),sc=Math.sin(c);
    return [[cc*cb,sc*cb,-sb],[cc*sb*sa-sc*ca,sc*sb*sa+cc*ca,cb*sa],[cc*sb*ca+sc*sa,sc*sb*ca-cc*sa,cb*ca]];
  }
  function corners(box){const axes=basis(box),out=[];for(const z of [-1,1])for(const y of [-1,1])for(const x of [-1,1])out.push(box.center.map((v,i)=>v+axes.reduce((sum,axis,k)=>sum+axis[i]*[x,y,z][k]*box.size[k]/2,0)));return out}
  function resize(box,axes,signs,delta,kind){
    const basis3=basis(box),h=kind==='top'?0:kind==='front'?0:1,v=kind==='top'?1:2;
    const a=basis3[axes[0]],b=basis3[axes[1]],det=a[h]*b[v]-b[h]*a[v];
    if(Math.abs(det)<.02)return null;
    const changes=[(delta[0]*b[v]-delta[1]*b[h])/det,(a[h]*delta[1]-a[v]*delta[0])/det];
    const result={size:[...box.size],center:[...box.center]};
    axes.forEach((axis,k)=>{result.size[axis]=Math.max(.05,box.size[axis]+signs[k]*changes[k]);const shift=signs[k]*(result.size[axis]-box.size[axis])/2;result.center=result.center.map((v,i)=>v+basis3[axis][i]*shift)});
    return result;
  }
  function rotate(box,kind,angle){
    const axis=kind==='top'?2:kind==='front'?1:0,t=kind==='front'?-angle:angle,c=Math.cos(t),s=Math.sin(t);
    const cols=basis(box).map(v=>axis===2?[c*v[0]-s*v[1],s*v[0]+c*v[1],v[2]]:axis===1?[c*v[0]+s*v[2],v[1],-s*v[0]+c*v[2]]:[v[0],c*v[1]-s*v[2],s*v[1]+c*v[2]]);
    const pitch=Math.asin(Math.max(-1,Math.min(1,-cols[0][2])));
    return Math.abs(Math.cos(pitch))<1e-6?{pitch,roll:0,yaw:Math.atan2(-cols[1][0],cols[1][1])}:{pitch,roll:Math.atan2(cols[1][2],cols[2][2]),yaw:Math.atan2(cols[0][1],cols[0][0])};
  }
  const api={basis,corners,resize,rotate,dot};if(typeof module!=='undefined'&&module.exports)module.exports=api;root.CuboidEdit=api;
})(typeof window!=='undefined'?window:globalThis);
