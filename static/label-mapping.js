(function(root){
  function defaultTarget(source,labels){const find=name=>labels.find(label=>label.toLowerCase()===name);return find(source.toLowerCase())||({car:find('vehicles')||find('vehicle'),motorcycle:find('two-wheels'),bicycle:find('two-wheels')}[source.toLowerCase()])||'__skip__'}
  const api={defaultTarget};if(typeof module!=='undefined')module.exports=api;else root.LabelMapping=api;
})(typeof globalThis!=='undefined'?globalThis:this);

// Camera labels use COCO names; keep exact job labels and existing LiDAR aliases.
(function(){const api=typeof module!=='undefined'?module.exports:LabelMapping,original=api.defaultTarget;api.defaultTarget=function(source,labels){const exact=original(source,labels);if(exact!=='__skip__')return exact;const aliases={person:['pedestrian','person'],dog:['animal'],cat:['animal'],horse:['animal'],cow:['animal'],sheep:['animal'],bird:['animal']};for(const name of aliases[source.toLowerCase()]||[]){const match=labels.find(label=>label.toLowerCase()===name);if(match)return match;}return '__skip__';};})();
