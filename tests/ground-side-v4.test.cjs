const assert=require('node:assert/strict');
const m=require('../static/solid-ground-math-v4.js');
const record={cell_size:2,cells:[[0,0,0,0,0],[1,0,0,0,0]],surface:[]};
assert.equal(m.referenceHeight(record),0);
assert.equal(m.sideVisible(record,[100,100,-1],1,{seal:true,style:'reference'}),false,'hide below even outside footprint');
assert.equal(m.sideVisible(record,[100,100,1],-1,{seal:true,style:'reference'}),false,'hide above even outside footprint');
assert.equal(m.sideVisible(record,[100,100,-1],-1,{seal:true,style:'reference'}),true);
assert.equal(m.sideVisible(record,[100,100,1],1,{seal:true,style:'reference'}),true);
assert.equal(m.sideVisible(record,[100,100,-1],1,{seal:true,xray:true}),true);
assert.equal(m.sideVisible(record,[100,100,-1],1,{seal:false}),true);
assert.equal(m.sideVisible(null,[0,0,-1],1,{seal:true}),true,'no invented floor without ground');
const slope={cell_size:2,cells:[[0,0,1,0,0]],surface:[]};
assert.equal(m.sideVisible(slope,[1,1,.5],1,{seal:true,style:'data'}),false,'use supported local slope');
assert.equal(m.sideVisible(slope,[1,1,1.5],1,{seal:true,style:'data'}),true);
console.log('Ground side isolation: outside footprint, both directions, local slope and xray passed');

assert.equal(m.sideVisible(record,[1,1,-1],-1,{seal:true,floorOnly:true}),false,'underside presentation hides native below-ground returns');
assert.equal(m.sideVisible(record,[1,1,1],1,{seal:true,floorOnly:true}),true);
assert.equal(m.sideVisible(record,[1,1,-1],-1,{seal:true,floorOnly:true,xray:true}),true);

assert.equal(m.sideVisible(record,[1,1,-1],-1,{seal:false,floorOnly:true}),false,'floor-only presentation independently hides labels and picking');
