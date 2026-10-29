// Pure playback model. Published restrictions remain separate from illustrative heights and timing.
export function altitudeValue(raw){return Number(raw.replace(/[@+\-]/g,'').replace('FL',''))*(raw.includes('FL')?100:1)}
export function constraintLabel(raw){if(!raw)return 'No published altitude at this fix';return ({'@':'At ','+':'At or above ','-':'At or below '}[raw[0]]||'')+(raw.includes('FL')?raw.slice(1):Number(raw.slice(1)).toLocaleString()+' ft')}
export function buildFlight(route,runway,fixes){
 const start=runway.start,end=runway.finish,lerp=t=>[start[0]+(end[0]-start[0])*t,start[1]+(end[1]-start[1])*t];
 const points=[{name:runway.id+' threshold',xz:start,altFt:0,ground:true,kind:'ground start'},{name:'Departure roll',xz:lerp(.60),altFt:0,ground:true,kind:'illustrative ground point'},{name:'Lift-off',xz:lerp(.94),altFt:250,kind:'illustrative take-off point'}];
 let height=runway.id==='34C'?2200:runway.id==='34L'?1800:900;
 for(let i=0;i<route.legs.length;i++){
  const leg=route.legs[i];if(i>0)height+=2400;
  if(leg.altitude){const limit=altitudeValue(leg.altitude);height=leg.altitude[0]==='@'?limit:leg.altitude[0]==='+'?Math.max(height,limit):Math.min(height,limit)}
  // Look ahead to an upper or exact limit so the illustrative profile does not overshoot it.
  for(const future of route.legs.slice(i+1)){if(future.altitude[0]==='-'||future.altitude[0]==='@'){height=Math.min(height,altitudeValue(future.altitude));break}}
  points.push({name:leg.fix,xz:fixes[leg.fix].xz,altFt:height,kind:'published fix',...leg});
 }
 let elapsed=0;const segments=[];
 for(let i=1;i<points.length;i++){const a=points[i-1],b=points[i],distance=Math.hypot(b.xz[0]-a.xz[0],b.xz[1]-a.xz[1]);const duration=i===1?7:i===2?3:Math.max(3,distance/2.2);segments.push({a,b,start:elapsed,end:elapsed+duration,duration,distance});elapsed+=duration}
 return {route,points,segments,duration:elapsed};
}
export function sampleFlight(flight,elapsed){
 const t=Math.max(0,Math.min(elapsed,flight.duration));let index=flight.segments.findIndex(s=>t<s.end);if(index<0)index=flight.segments.length-1;
 const s=flight.segments[index],fraction=Math.max(0,Math.min(1,(t-s.start)/s.duration));
 return {x:s.a.xz[0]+(s.b.xz[0]-s.a.xz[0])*fraction,z:s.a.xz[1]+(s.b.xz[1]-s.a.xz[1])*fraction,altFt:s.a.altFt+(s.b.altFt-s.a.altFt)*fraction,index,fraction,next:s.b.name,heading:Math.atan2(-(s.b.xz[0]-s.a.xz[0]),-(s.b.xz[1]-s.a.xz[1])),ground:index===0,complete:t>=flight.duration};
}
export function advance(state,dt){
 if(!state.flight||!state.playing)return;
 const period=state.flight.duration+2;state.elapsed+=dt;
 if(state.elapsed>=period){if(state.loop){state.loops+=Math.floor(state.elapsed/period);state.elapsed%=period}else{state.elapsed=state.flight.duration;state.playing=false}}
}
