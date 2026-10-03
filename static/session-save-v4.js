/* Session-scoped snapshots prevent late saves from changing a different frame. */
(function(root){
  class SessionSaver{
    constructor(api,{onSaved=()=>{},onError=()=>{},onBusy=()=>{}}={}){this.api=api;this.onSaved=onSaved;this.onError=onError;this.onBusy=onBusy;this.queue=new Map();this.running=null;}
    save(session){
      if(!session)return Promise.resolve();this.queue.set(session.id,{session,boxes:structuredClone(session.boxes)});
      if(!this.running){this.onBusy(true);this.running=this.drain().finally(()=>{this.running=null;this.onBusy(false);});}return this.running;
    }
    async drain(){
      while(this.queue.size){const [id,item]=this.queue.entries().next().value;this.queue.delete(id);
        try{const result=await this.api('/api/sessions/'+id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:item.session.revision,boxes:item.boxes})});item.session.revision=result.revision;this.onSaved(item.session);}
        catch(error){this.queue.delete(id);this.onError(error,item.session);}
      }
    }
  }
  const exported={SessionSaver};if(typeof module!=='undefined')module.exports=exported;root.V4SessionSave=exported;
  if(typeof document!=='undefined'){
    const saver=new SessionSaver(api,{onBusy:busy=>{state.saving=busy;updateReviewUI();},onSaved:session=>{if(state.session?.id===session.id){state.session.revision=session.revision;$('save-state').textContent='Đã lưu · r'+session.revision;renderList();V4App.selectionChanged();}},onError:(error,session)=>{if(state.session?.id===session.id){$('save-state').textContent='Lưu lỗi';fail(error);}else message('Lưu phiên '+session.id.slice(0,8)+' lỗi: '+error.message,true);}});
    save=()=>saver.save(state.session);
    function clearReports(){for(const [id,text] of [['v4-quality-status','Kiểm tra box trong frame hiện tại.'],['v4-measure-status','Chọn box A để đo.'],['v4-eval-status','']]){const node=$(id);if(node)node.textContent=text;}if($('v4-eval-run'))$('v4-eval-run').disabled=true;if($('v4-eval-file'))$('v4-eval-file').value='';}
    const originalSession=V4App.sessionChanged;V4App.sessionChanged=async data=>{clearReports();await originalSession(data);};
    $('v4-units').addEventListener('change',clearReports);
    const originalSelection=V4App.selectionChanged;V4App.selectionChanged=async()=>{if($('v4-measure-status'))$('v4-measure-status').textContent='Chọn hai box rồi đo khoảng cách.';await originalSelection();};
  }
})(globalThis);
