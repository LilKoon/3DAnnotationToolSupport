const assert=require('node:assert/strict');
const nav=require('../static/navigation.js');
const dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0);
for(const yaw of [-2,-.6,0,1.7])for(const elevation of [-1.4,0,.68,1.4]){
  const basis=nav.basis(yaw,elevation),scale=13,dx=80,dy=-35;
  const delta=nav.screenDelta(dx,dy,scale,yaw,elevation);
  assert.ok(Math.abs(dot(delta,basis.right)*scale-dx)<1e-8);
  assert.ok(Math.abs(-dot(delta,basis.up)*scale-dy)<1e-8);
  for(let axis=0;axis<3;axis++){
    const x=basis.right[axis]*scale,y=-basis.up[axis]*scale;
    if(x*x+y*y<1e-6)assert.equal(nav.axisDelta(10,10,axis,scale,yaw,elevation),0);
    else assert.ok(Math.abs(nav.axisDelta(2*x,2*y,axis,scale,yaw,elevation)-2)<1e-8);
  }
  for(const boxYaw of [-1.2,.7,2])for(const sign of [-1,1]){
    const axis=[Math.cos(boxYaw)*sign,Math.sin(boxYaw)*sign,0],x=dot(axis,basis.right)*scale,y=-dot(axis,basis.up)*scale;
    if(x*x+y*y>1e-6)assert.ok(Math.abs(nav.axisDelta(2*x,2*y,axis,scale,yaw,elevation)-2)<1e-8);
  }
}
console.log('Navigation: pan and XYZ drag match projected movement across camera angles.');
