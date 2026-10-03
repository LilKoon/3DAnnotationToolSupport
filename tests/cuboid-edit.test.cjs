const assert=require('node:assert/strict'),E=require('../static/cuboid-edit.js');
const box={center:[1,2,3],size:[4,2,1],yaw:.4,pitch:.3,roll:-.2};
const axes=E.basis(box);for(const a of axes)assert.ok(Math.abs(E.dot(a,a)-1)<1e-12);
for(const kind of ['top','front','side']){
  const rotated=E.rotate(box,kind,.2),back=E.rotate({...box,...rotated},kind,-.2);
  E.basis({...box,...back}).forEach((a,i)=>a.forEach((v,j)=>assert.ok(Math.abs(v-axes[i][j])<1e-10)));
  const indices=kind==='top'?[0,1]:kind==='front'?[0,2]:[1,2],h=kind==='side'?1:0,v=kind==='top'?1:2;
  for(const x of [-1,1])for(const y of [-1,1]){
    const delta=[axes[indices[0]][h]*.4+axes[indices[1]][h]*.2,axes[indices[0]][v]*.4+axes[indices[1]][v]*.2];
    const changed=E.resize(box,indices,[x,y],delta,kind);assert.ok(changed);
    const opposite=b=>b.center.map((value,i)=>value-axes[indices[0]][i]*x*b.size[indices[0]]/2-axes[indices[1]][i]*y*b.size[indices[1]]/2);
    opposite(changed).forEach((value,i)=>assert.ok(Math.abs(value-opposite(box)[i])<1e-10));
  }
}
assert.equal(E.corners(box).length,8);console.log('Cuboid editing: full rotation, four corners and fixed opposite corners passed.');
