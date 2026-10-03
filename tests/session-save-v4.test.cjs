const assert=require('node:assert/strict');const {SessionSaver}=require('../static/session-save-v4.js');
(async()=>{
  let resolve;const requests=[];const old={id:'old',revision:1,boxes:[{id:'a',center:[0,0,0]}]};const current={id:'new',revision:8,boxes:[]};
  const saver=new SessionSaver(async(path,options)=>{requests.push(JSON.parse(options.body));return await new Promise(r=>resolve=r);});
  const promise=saver.save(old);await new Promise(r=>setImmediate(r));resolve({revision:2});await promise;
  assert.equal(old.revision,2);assert.equal(current.revision,8);assert.equal(requests[0].boxes[0].id,'a');
  let unlock;const calls=[];const next=new SessionSaver(async(path,options)=>{const payload=JSON.parse(options.body);calls.push(payload);if(calls.length===1)await new Promise(r=>unlock=r);return {revision:payload.revision+1};});
  const s={id:'same',revision:0,boxes:[{id:'first'}]};const running=next.save(s);s.boxes=[{id:'second'}];next.save(s);s.boxes=[{id:'latest'}];next.save(s);unlock();await running;
  assert.equal(calls.length,2);assert.equal(calls[1].boxes[0].id,'latest');assert.equal(calls[1].revision,1);assert.equal(s.revision,2);
  console.log('Session saves: snapshots, coalescing and revision isolation passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
