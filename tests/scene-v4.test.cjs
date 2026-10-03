const assert=require('node:assert/strict');const scene=require('../static/scene-v4.js');
const state={v4Scene:{mode:'hide',focus:false,maxRange:100,zMin:null,zMax:null},v4Ground:{display_mask:[1,0,2]}};
assert.equal(scene.visible([1,1,0],0,'main',state),false);
assert.equal(scene.visible([1,1,0],1,'main',state),true);
assert.equal(scene.visible([1,1,0],2,'main',state),true);
state.v4Scene.mode='dim';assert.equal(scene.alpha(0,state),.12);assert.equal(scene.alpha(1,state),1);
state.v4Scene.mode='raw';state.v4Scene.maxRange=5;assert.equal(scene.visible([9,0,0],2,'main',state),false);
state.v4Scene.focus=true;state.selected='a';state.session={boxes:[{id:'a',center:[0,0,0],size:[2,2,2],yaw:Math.PI/4}]};
assert.equal(scene.visible([0,0,0],2,'main',state),true);assert.equal(scene.visible([4,0,0],2,'main',state),false);
console.log('Scene: raw/dim/hide/unknown/ROI/range passed');

state.v4Scene.focus=false;state.v4Scene.maxRange=Infinity;state.v4Scene.zMin=.5;state.v4Scene.zMax=2;
assert.equal(scene.visible([0,0,0],2,'main',state),false);assert.equal(scene.visible([0,0,1],2,'main',state),true);
console.log('Height filtering passed');
