// Publish always targets the job bound to the current annotation session.
(function(root){
  function publishPayload(binding,credentials){
    if(!binding?.url||!Number.isInteger(binding.job_id)||binding.job_id<=0)throw new Error('Phiên chưa có kết nối CVAT hợp lệ. Hãy nhập lại frame từ CVAT.');
    if(!credentials.username.trim()||!credentials.password)throw new Error('Nhập lại tài khoản và mật khẩu trong “Kết nối CVAT job” trước khi publish.');
    return {url:binding.url,job_id:binding.job_id,username:credentials.username.trim(),password:credentials.password,verify_ssl:credentials.verify_ssl!==false,confirm:true};
  }
  function errorMessage(detail,status){
    if(Array.isArray(detail))return detail.map(item=>`${(item.loc||[]).filter(part=>part!=='body').join('.')||'Dữ liệu'}: ${item.msg||'không hợp lệ'}`).join('; ');
    return typeof detail==='string'?detail:`HTTP ${status}`;
  }
  const api={publishPayload,errorMessage};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  root.CVATClient=api;
})(typeof window!=='undefined'?window:globalThis);
