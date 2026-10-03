/* WebGL depth renderer composed into the established 2D editor canvas. */
(function(root){
 const vertex=`
 attribute vec3 aPosition;attribute vec3 aColor;attribute float aMask;attribute vec2 aHeight;
 uniform vec3 uMid,uRight,uUp,uDepth,uBoxCenter,uAxis0,uAxis1,uAxis2,uHalf;
 uniform vec2 uScale,uZ;uniform float uDepthScale,uPointSize,uRange,uFocus,uMode,uRelative,uBias;
 varying vec3 vColor,vWorld;varying float vMask;varying vec2 vHeight;
 void main(){vec3 p=aPosition-uMid;gl_Position=vec4(dot(p,uRight)*uScale.x,dot(p,uUp)*uScale.y,dot(p,uDepth)*uDepthScale-uBias,1.0);gl_PointSize=uPointSize;vColor=aColor;vWorld=aPosition;vMask=aMask;vHeight=aHeight;}
 `;
 const fragment=`
 precision highp float;
 uniform float uUnderFloor;
 uniform float uSeal,uSide,uReference,uFloor;
 uniform vec2 uZ;uniform vec3 uBoxCenter,uAxis0,uAxis1,uAxis2,uHalf;
 uniform float uRange,uFocus,uMode,uRelative,uKind,uXray;
 varying vec3 vColor,vWorld;varying float vMask;varying vec2 vHeight;
 void main(){
  if(uUnderFloor>.5&&uXray<.5&&(uKind<.5||uKind>1.5))discard;
  if(uKind<.5||uKind>1.5){
   float groundHeight=uReference>.5||vHeight.y<.5?uFloor:vWorld.z-vHeight.x;
   if(uSeal>.5&&uXray<.5&&(vWorld.z-groundHeight)*uSide<-.025)discard;
  }
  if(!(uKind>.5&&uKind<1.5&&uSeal>.5&&uXray<.5)){
  if(length(vWorld.xy)>uRange)discard;
  float h=uRelative>.5?vHeight.x:vWorld.z;
  if((uRelative<.5||vHeight.y>.5)&&(h<uZ.x||h>uZ.y))discard;
  if(uFocus>.5){vec3 d=vWorld-uBoxCenter;if(abs(dot(d,uAxis0))>uHalf.x||abs(dot(d,uAxis1))>uHalf.y||abs(dot(d,uAxis2))>uHalf.z)discard;}
  }
  if(uKind<.5){if(uMode>1.5&&vMask>.5&&vMask<1.5)discard;float alpha=uMode>.5&&uMode<1.5&&vMask>.5&&vMask<1.5?.12:1.0;gl_FragColor=vec4(vColor,alpha);}
  else if(uKind<1.5){vec3 color=gl_FrontFacing?vec3(.25,.36,.39):vec3(.18,.12,.10);
   vec2 grid=abs(fract(vWorld.xy/2.0)-.5);if(max(grid.x,grid.y)>.485)color*=1.22;
   if(!gl_FrontFacing&&mod(gl_FragCoord.x+gl_FragCoord.y,16.0)<3.0)color*=1.5;
   gl_FragColor=vec4(color,uXray>.5?.22:1.0);}
  else gl_FragColor=vec4(vColor,1.0);
 }`;
 class DepthRenderer{
  constructor(){this.canvas=document.createElement('canvas');this.gl=this.canvas.getContext('webgl',{alpha:false,antialias:true,preserveDrawingBuffer:true});if(!this.gl)throw Error('WebGL không khả dụng');
   this.canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();this.lost=true;render();});this.canvas.addEventListener('webglcontextrestored',()=>{this.lost=false;this.init();this.cloudKey=null;render();});this.init();}
  init(){const gl=this.gl;const shader=(type,source)=>{const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s;};
   this.program=gl.createProgram();gl.attachShader(this.program,shader(gl.VERTEX_SHADER,vertex));gl.attachShader(this.program,shader(gl.FRAGMENT_SHADER,fragment));gl.linkProgram(this.program);if(!gl.getProgramParameter(this.program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(this.program));gl.useProgram(this.program);
   this.locations={};this.attributes={};for(const name of ['aPosition','aColor','aMask','aHeight'])this.attributes[name]=gl.getAttribLocation(this.program,name);
   this.pointBuffer=gl.createBuffer();this.dynamicBuffer=gl.createBuffer();}
  uniform(name,value){const gl=this.gl;const l=this.locations[name]??=(gl.getUniformLocation(this.program,name));if(l===null)return;if(Array.isArray(value)){if(value.length===2)gl.uniform2fv(l,value);else gl.uniform3fv(l,value);}else gl.uniform1f(l,value);}
  bind(buffer){const gl=this.gl;gl.bindBuffer(gl.ARRAY_BUFFER,buffer);for(const [name,size,offset] of [['aPosition',3,0],['aColor',3,12],['aMask',1,24],['aHeight',2,28]]){const loc=this.attributes[name];if(loc>=0){gl.enableVertexAttribArray(loc);gl.vertexAttribPointer(loc,size,gl.FLOAT,false,36,offset);}}}
  uploadCloud(s){
   if(this.cloudKey===s.points&&this.colorKey===s.pointColorMode&&this.groundKey===s.v4Ground)return;
   const cells=new Map((s.v4Ground?.cells||[]).map(c=>[c[0]+','+c[1],c])),size=s.v4Ground?.cell_size;
   const data=new Float32Array(s.points.length*9);
   s.points.forEach((p,i)=>{const rgb=s.pointColorMode!=='uniform'?s.pointColors?.[i]:null,c=size?cells.get(Math.floor(p[0]/size)+','+Math.floor(p[1]/size)):null,rel=c?p[2]-(c[2]*p[0]+c[3]*p[1]+c[4]):0;
    data.set([p[0],p[1],p[2],...(rgb?rgb.map(v=>v/255):[.79,.86,.87]),s.v4Ground?.display_mask?.[i]||0,rel,c?1:0],i*9);});
   this.bind(this.pointBuffer);this.gl.bufferData(this.gl.ARRAY_BUFFER,data,this.gl.STATIC_DRAW);
   this.cloudKey=s.points;this.colorKey=s.pointColorMode;this.groundKey=s.v4Ground;
  }
  drawVertices(points,colors,type,kind,bias=0){
   if(!points.length)return;const gl=this.gl,data=new Float32Array(points.length*9);
   points.forEach((p,i)=>data.set([...p,...(Array.isArray(colors[0])?colors[i]:colors),0,0,0],i*9));
   if(kind===2&&this.activeState?.v4Ground){
    const record=this.activeState.v4Ground;
    points.forEach((p,i)=>{const z=SolidGroundMath.height(record,p);if(z!==null){data[i*9+7]=p[2]-z;data[i*9+8]=1;}});
   }
   if(kind===1)for(let i=0;i<points.length;i++)data[i*9+8]=1;
   this.bind(this.dynamicBuffer);gl.bufferData(gl.ARRAY_BUFFER,data,gl.DYNAMIC_DRAW);this.uniform('uKind',kind);this.uniform('uBias',bias);gl.drawArrays(type,0,points.length);
  }
  draw(g,s,mesh,options){
   if(this.lost)throw Error('WebGL context bị mất; đang dùng chế độ dự phòng');
   this.activeState=s;
   const gl=this.gl,dpr=window.devicePixelRatio||1,w=Math.round(g.w*dpr),h=Math.round(g.h*dpr);
   if(this.canvas.width!==w||this.canvas.height!==h){this.canvas.width=w;this.canvas.height=h;}
   gl.viewport(0,0,w,h);gl.useProgram(this.program);gl.clearColor(.059,.098,.141,1);gl.clearDepth(1);gl.depthMask(true);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
   gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);gl.disable(gl.CULL_FACE);gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);
   const c=Math.cos(s.yaw),sn=Math.sin(s.yaw),e=Math.sin(s.elevation),v=Math.cos(s.elevation),right=[c,sn,0],up=[-sn*e,c*e,v],depth=[-sn*v,c*v,-e];
   const span=Math.max(30,(s.bounds?.range||30)+Math.hypot(...g.mid.map((x,i)=>x-(s.bounds?.mid?.[i]||0))));
   for(const [name,value] of Object.entries({uMid:g.mid,uRight:right,uUp:up,uDepth:depth,uScale:[g.scale*2/g.w,g.scale*2/g.h],uDepthScale:1/span,uPointSize:s.pointSize*dpr,uRange:Number.isFinite(s.v4Scene.maxRange)?s.v4Scene.maxRange:1e20,uZ:[s.v4Scene.zMin??-1e20,s.v4Scene.zMax??1e20],uMode:{raw:0,dim:1,hide:2,surface:3}[s.v4Scene.mode],uRelative:options.relative?1:0,uXray:options.xray?1:0,uFocus:s.v4Scene.focus&&selected()?1:0}))this.uniform(name,value);
   const floor=SolidGroundMath.referenceHeight(s.v4Ground);
   this.uniform('uUnderFloor',options.floorOnly&&s.elevation<0&&floor!==null&&s.v4Scene.mode==='surface'?1:0);
   this.uniform('uSeal',options.seal&&floor!==null&&s.v4Scene.mode==='surface'?1:0);
   this.uniform('uSide',s.elevation<0?-1:1);this.uniform('uReference',mesh.reference?1:0);this.uniform('uFloor',floor??0);
   const box=selected(),axes=box?CuboidEdit.basis(box):[[1,0,0],[0,1,0],[0,0,1]];
   this.uniform('uBoxCenter',box?.center||[0,0,0]);axes.forEach((a,i)=>this.uniform('uAxis'+i,a));this.uniform('uHalf',box?box.size.map(x=>x/2+1):[1,1,1]);
   if(s.v4Scene.mode==='surface'){
    gl.depthMask(!options.xray);this.drawVertices(mesh.triangles.flat(),[1,1,1],gl.TRIANGLES,1);gl.depthMask(true);
   }
   if(options.xray)gl.disable(gl.DEPTH_TEST);
   this.uploadCloud(s);this.bind(this.pointBuffer);this.uniform('uKind',0);this.uniform('uBias',0);gl.drawArrays(gl.POINTS,0,s.points.length);
   const vertices=[],colors=[];
   for(const b of s.session?.boxes||[]){
    if(b.status==='rejected'&&b.id!==s.selected)continue;
    const active=b.id===s.selected,hex=s.session.label_specs?.find(l=>l.name===b.label)?.color|| (b.status==='accepted'?'#52d4ab':'#e99b60');
    const rgb=/^#[0-9a-f]{6}$/i.test(hex)?[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)/255):[.9,.6,.3],pts=CuboidEdit.corners(b);
    for(const [i,j] of edges){vertices.push(pts[i],pts[j]);colors.push(rgb,rgb);}
    if(active||options.details||options.axes)for(let axis=0;axis<3;axis++){vertices.push(b.center,axisEnd(b,axis));const col=[[.96,.43,.45],[.44,.84,.49],[.37,.69,1]][axis];colors.push(col,col);}
    if(options.footprints&&s.v4Ground){
     const footprint=pts.slice(0,4).map(p=>{const z=SolidGroundMath.height(s.v4Ground,p);return z===null?null:[p[0],p[1],z+.035];});
     if(footprint.every(Boolean))for(const [i,j] of [[0,1],[1,3],[3,2],[2,0]]){vertices.push(footprint[i],footprint[j]);colors.push(rgb,rgb);}
    }
   }
   this.drawVertices(vertices,colors,gl.LINES,2,.00004);
   gl.flush();g.ctx.globalAlpha=1;g.ctx.drawImage(this.canvas,0,0,g.w,g.h);
   return {renderer:'webgl',triangles:mesh.triangles.length,filled:mesh.filled,points:s.points.length,depth:!options.xray,span};
  }
 }
 root.SolidGroundGL={DepthRenderer};
})(globalThis);
