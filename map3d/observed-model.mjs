// Recorded UTC samples. No climb generator, inferred SID, or invented gap continuity.
export function sampleObserved(samples, timestamp, maximumGapSeconds=15){
 if(!samples.length||timestamp<samples[0][0]||timestamp>samples.at(-1)[0])return {available:false,reason:'outside observed interval'};
 let lo=0,hi=samples.length-1;
 while(lo<hi){const mid=(lo+hi)>>1;if(samples[mid][0]<timestamp)lo=mid+1;else hi=mid}
 const b=samples[lo];
 if(b[0]===timestamp)return measurement(b,false);
 const a=samples[lo-1],gap=(b[0]-a[0])/1000;
 if(gap>maximumGapSeconds)return {available:false,reason:'observation gap',gapSeconds:gap,previousMs:a[0],nextMs:b[0]};
 const t=(timestamp-a[0])/(b[0]-a[0]);
 const lerp=(x,y)=>x===null||y===null?null:x+(y-x)*t;
 let heading=a[6];if(heading!==null&&b[6]!==null)heading=(heading+(((b[6]-heading+540)%360)-180)*t+360)%360;
 const result=measurement([timestamp,lerp(a[1],b[1]),lerp(a[2],b[2]),lerp(a[3],b[3]),lerp(a[4],b[4]),lerp(a[5],b[5]),heading,null,'display interpolation',null],true);
 if(result.trackDeg===null)result.trackDeg=(Math.atan2(b[1]-a[1],-(b[2]-a[2]))*180/Math.PI+360)%360;
 return result;
}
function measurement(s,interpolated){
 const altitudeFt=s[3]??s[4];
 return {available:true,timestampMs:s[0],x:s[1],z:s[2],altitudeFt,barometricAltitudeFt:s[3],geometricAltitudeFt:s[4],altitudeReference:s[3]!==null?'pressure':'WGS84 ellipsoid',displayAltitudeFt:altitudeFt===null?null:altitudeFt-(s[3]!==null?50:65),groundSpeedKt:s[5],trackDeg:s[6],onGround:s[7],qualityFlags:s[8],observationId:s[9],interpolated};
}
export function splitObservedTrack(samples,maximumGapSeconds=15){
 const groups=[];
 for(const s of samples){if(!groups.length||s[0]-groups.at(-1).at(-1)[0]>maximumGapSeconds*1000)groups.push([]);groups.at(-1).push(s)}
 return groups;
}
export function advanceObserved(state,deltaSeconds){
 if(!state.playing)return;
 state.timestampMs=Math.min(state.endMs,state.timestampMs+deltaSeconds*1000*state.speed);
 if(state.timestampMs>=state.endMs)state.playing=false;
}
export function activeFlights(flights,timestampMs,runway='',status=''){
 return flights.filter(f=>(!runway||f.runway===runway)&&(!status||f.match_status===status)&&f.start_ms<=timestampMs&&timestampMs<=f.end_ms);
}
