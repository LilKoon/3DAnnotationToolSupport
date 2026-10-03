const assert=require('node:assert/strict');const mapping=require('../static/label-mapping.js');
assert.equal(mapping.defaultTarget('person',['car','pedestrian']),'pedestrian');assert.equal(mapping.defaultTarget('car',['vehicles']),'vehicles');assert.equal(mapping.defaultTarget('traffic light',['car','pedestrian']),'__skip__');console.log('Image label aliases preserve LiDAR mapping');
