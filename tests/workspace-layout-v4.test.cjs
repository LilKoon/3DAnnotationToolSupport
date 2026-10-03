const assert=require('node:assert/strict'),m=require('../static/workspace-layout-model-v4.js');
for(const w of [320,768,1024,1440]){
 const initial=m.normalize(null,w);assert.equal(initial.right,false);
 const left=m.open(initial,'left','display',w);assert.equal(left.left,true);assert.equal(left.leftPage,'display');
 const right=m.open(left,'right','camera',w);assert.equal(right.right,true);if(w<1200)assert.equal(right.left,false);
 const close=m.open(right,'right','camera',w);assert.equal(close.right,false);
 assert.deepEqual(m.open(close,'right','invalid',w),close);
}
const recovered=m.normalize({left:'oops',right:1,leftPage:'invalid',rightPage:'camera',projections:false},768);
assert.equal(recovered.left,false);assert.equal(recovered.right,false);assert.equal(recovered.leftPage,'data');assert.equal(recovered.rightPage,'camera');assert.equal(recovered.projections,false);
assert.equal(m.normalize({left:true,right:true},320).right,false);
console.log('Workspace layout: group switching, independent collapse, narrow mutual exclusion and corrupt preference recovery passed');
