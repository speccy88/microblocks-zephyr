// SPDX-License-Identifier: MIT
const assert=require('node:assert/strict');
const {fixture}=require('./gp_sensor_fixture.cjs');
module.exports=function(trees){
 let now=1000;
 const f=fixture(trees,{hooks:{millisOp:()=>now,millisSince:start=>now-start}});
 const rmc='$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A';
 const gga='$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47';
 assert.equal(f.call('_gpsChecksumOK',rmc),true);assert.equal(f.call('_gpsChecksumOK',gga),true);
 assert.equal(f.call('_gpsChecksumOK',rmc.slice(0,-2)+'00'),false);
 assert.equal(f.call('_gpsChecksumOK',rmc+'garbage'),false);
 assert.equal(f.call('_gpsChecksumOK',rmc.slice(0,-2)+'ZZ'),false);
 f.call('_gpsProcessSentence',rmc);
 assert.equal(f.globals._gpsFixed,true);assert.equal(f.globals._gpsLat,48117300);assert.equal(f.globals._gpsLon,11516666);
 assert.equal(f.globals._gpsSpeedKmph,4148);assert.equal(f.globals._gpsCourse,8440);assert.equal(f.globals._gpsYear,1994);
 f.call('_gpsProcessSentence',gga);assert.equal(f.globals._gpsAltitude,54540);assert.equal(f.globals._gpsSatellites,8);
 assert.equal(f.call('_gpsCoordinate','3723.2475','S'),-37387458);
 assert.equal(f.call('_gpsCoordinateOK','4860.000','N'),false);
 assert.equal(f.call('_gpsCoordinateOK','9100.000','N'),false);
 assert.equal(f.call('_gpsCoordinateOK','18100.000','W'),false);
 assert.equal(f.call('_gpsCoordinateOK','4807.000','Q'),false);
 const fields=['$GNGGA','123519','4807.038','N','01131.000','E','0','00','0','0'];
 f.call('_gpsParseGGA',fields);assert.equal(f.globals._gpsFixed,false);
 f.call('_gpsProcessSentence',rmc);now+=10001;assert.equal(f.call('gpsValidPosition'),false);
 return {RMC:true,GGA:true,checksum:true,coordinate_bounds:true,invalid_fix:true,stale_fix:true,physical:false};
};
