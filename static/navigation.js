// Orthographic camera basis shared by drawing, panning and XYZ gizmo drags.
const Navigation3D = (() => {
  function basis(yaw, elevation) {
    const c=Math.cos(yaw),s=Math.sin(yaw),e=Math.sin(elevation),v=Math.cos(elevation);
    return {right:[c,s,0],up:[-s*e,c*e,v]};
  }
  function screenDelta(dx,dy,scale,yaw,elevation) {
    const {right,up}=basis(yaw,elevation);
    return right.map((value,i)=>(dx*value-dy*up[i])/scale);
  }
  function axisDelta(dx,dy,axis,scale,yaw,elevation) {
    const {right,up}=basis(yaw,elevation),vector=Array.isArray(axis)?axis:[0,1,2].map(i=>i===axis?1:0),dot=(a,b)=>a.reduce((sum,value,i)=>sum+value*b[i],0),x=dot(right,vector)*scale,y=-dot(up,vector)*scale;
    const length=x*x+y*y;
    return length < 1e-6 ? 0 : (dx*x+dy*y)/length;
  }
  function objectAxis(box,axis){
    const editor=typeof CuboidEdit!=='undefined'?CuboidEdit:require('./cuboid-edit.js');
    const geometric=(box.axis_order||[0,1,2])[axis],sign=(box.axis_signs||[1,1,1])[axis];
    return editor.basis(box)[geometric].map(v=>v*sign);
  }
  return {basis,screenDelta,axisDelta,objectAxis};
})();
if(typeof module!=='undefined')module.exports=Navigation3D;
