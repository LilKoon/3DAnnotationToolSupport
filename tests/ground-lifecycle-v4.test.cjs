const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
(async()=>{
 const nodes={};const $=id=>nodes[id]??=( {value:'raw',textContent:'',disabled:false,onclick:()=>{},onchange:()=>{}} );
 const state={session:{id:'a'},v4Ground:{surface:[[1]]},v4Scene:{mode:'surface',maxRange:Infinity}};
 $('v4-ground-mode').value='surface';$('v4-ground-status').textContent='ground ready';
 const ctx={state,$,render:()=>{},globalThis:null,V4App:{sessionChanged:async()=>{state.v4Ground=null;state.v4Scene.mode='raw';$('v4-ground-mode').value='raw';$('v4-ground-status').textContent='';},scan:async()=>{state.v4Ground={surface:[[2]]};state.v4Scene.mode='dim';$('v4-ground-mode').value='dim';}}};ctx.globalThis=ctx;
 const source=fs.readFileSync(require.resolve('../static/assist-v4.js'),'utf8'),marker='// Ground lifecycle fix:';
 assert.ok(source.includes(marker),'ground lifecycle fix is installed');vm.runInNewContext(source.slice(source.indexOf(marker)),ctx);
 const ground=state.v4Ground;await ctx.V4App.sessionChanged({id:'a'});
 assert.equal(state.v4Ground,ground);assert.equal(state.v4Scene.mode,'surface');assert.equal($('v4-ground-mode').value,'surface');
 state.session={id:'b'};await ctx.V4App.sessionChanged({id:'b'});assert.equal(state.v4Ground,null);assert.equal(state.v4Scene.mode,'raw');
 $('v4-ground-mode').value='surface';await $('v4-ground-mode').onchange();assert.ok(state.v4Ground);assert.equal(state.v4Scene.mode,'surface');
 $('v4-ground-mode').value='hide';await $('v4-ground-mode').onchange();assert.equal(state.v4Scene.mode,'hide');await $('v4-ground-run').onclick();assert.equal(state.v4Scene.mode,'hide');
 state.v4Ground=null;let finish;ctx.V4App.scan=()=>new Promise(resolve=>{finish=()=>{state.v4Ground={surface:[]};state.v4Scene.mode='dim';resolve();};});
 $('v4-ground-mode').value='surface';const pending=$('v4-ground-mode').onchange();$('v4-ground-mode').value='raw';await $('v4-ground-mode').onchange();finish();await pending;assert.equal(state.v4Scene.mode,'raw');
 console.log('Ground lifecycle: same frame after detect, new frame reset, lazy scan, mode preservation and pending raw choice passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
