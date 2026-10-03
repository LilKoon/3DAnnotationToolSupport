/* V4 review backups include sensor metadata; restoration always creates a new session. */
(function(){
  $('btn-export').onclick=async()=>{if(!state.session)return;const id=state.session.id;try{const data=await api(`/api/v4/sessions/${id}/review-backup`);const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download=`v4-review-${id}.json`;link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);}catch(error){fail(error);}};
  $('file-import').onchange=async event=>{const file=event.target.files[0];if(!file||!state.session)return;const id=state.session.id;try{let data=JSON.parse(await file.text());if(data.format!=='v4-review'){if(!Array.isArray(data.boxes))throw Error('Backup không có boxes');const current=await api(`/api/v4/sessions/${id}/review-backup`);data={...current,session:{...current.session,boxes:data.boxes}};}
    const result=await api(`/api/v4/sessions/${id}/restore-review`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});if(state.session?.id!==id)return;await openSession(result.id);message('Đã khôi phục thành phiên V4 mới; phiên cũ được giữ nguyên.');}catch(error){fail(error);}};
  $('file-import').parentElement.title='Khôi phục thành phiên mới; mở đúng point cloud trước khi import backup';
})();
