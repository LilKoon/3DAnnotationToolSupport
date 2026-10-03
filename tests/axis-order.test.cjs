const assert=require('node:assert/strict');
const nav=require('../static/navigation.js');
const orders=[[0,1,2],[0,2,1],[1,0,2],[1,2,0],[2,0,1],[2,1,0]];
const dot=(a,b)=>a.reduce((sum,v,i)=>sum+v*b[i],0);
for(const order of orders)for(const yaw of [-1.2,0,.7]){
  const box={center:[1,2,3],size:[4,2,1],yaw,axis_order:order,axis_signs:[-1,1,-1]};
  const original=JSON.stringify(box),axes=[0,1,2].map(i=>nav.objectAxis(box,i));
  for(let i=0;i<3;i++){
    assert.ok(Math.abs(dot(axes[i],axes[i])-1)<1e-8);
    for(let j=0;j<i;j++)assert.ok(Math.abs(dot(axes[i],axes[j]))<1e-8);
    const basis=nav.basis(-.6,.68),dx=dot(axes[i],basis.right)*20,dy=-dot(axes[i],basis.up)*20;
    assert.ok(Math.abs(nav.axisDelta(dx,dy,axes[i],20,-.6,.68)-1)<1e-8);
  }
  assert.equal(JSON.stringify(box),original);
}
assert.deepEqual(nav.objectAxis({yaw:0,axis_order:[2,1,0],axis_signs:[1,1,1]},0),[0,0,1]);
console.log('All 6 axis permutations: orthogonal axes, signed directions and gizmo movement verified.');
