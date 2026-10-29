import * as THREE from 'three';
import {sampleObserved,splitObservedTrack,advanceObserved,activeFlights} from './observed-model.mjs';

const colors={'34C':'#168d9b','34L':'#bb4b76',unknown:'#9d751d'};
const utc=ms=>new Date(ms).toISOString().slice(11,23)+' UTC';
const element=(tag,text,className)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(className)e.className=className;return e};

export function mountObserved({scene,data,aircraft,host,vertical,onMode,camera,controls}){
 const state={enabled:false,playing:false,speed:20,timestampMs:0,endMs:0,runway:'',status:'',hour:'',selected:null,manifest:null,includeOther:false};
 const flights=new Map(),pending=new Set(),failed=new Set(),group=new THREE.Group();group.visible=false;scene.add(group);
 const modeLabel=element('label','FLIGHT MODE','observed-mode');
 const mode=element('select');mode.setAttribute('aria-label','Flight mode');
 for(const [value,title] of [['illustrative','Published procedure demo'],['observed','Recorded flights · local A2']]){const o=element('option',title);o.value=value;mode.append(o)}
 modeLabel.append(mode);document.querySelector('.section-head').prepend(modeLabel);
 const panel=element('section',undefined,'observed-panel');panel.hidden=true;panel.setAttribute('aria-label','Recorded flight controls');
 panel.append(element('h2','Observed departures'),element('p','Recorded UTC positions with geometric SID candidates. Assigned clearances are unknown.','observed-intro'));
 const notice=element('p','Loading the local dataset…','observed-notice');notice.setAttribute('role','status');panel.append(notice);
 const filters=element('div',undefined,'observed-filters');
 function select(label,values,change){const field=element('label',label);const input=element('select');input.setAttribute('aria-label',label);for(const [v,title] of values){const o=element('option',title);o.value=v;input.append(o)}input.onchange=()=>change(input.value);field.append(input);filters.append(field);return input}
 select('Runway',[['','Both runways'],['34C','34C'],['34L','34L']],v=>{state.runway=v;renderList()});
 select('Match status',[['','All statuses'],...['geometry_consistent','ambiguous','partial','unmatched','insufficient_data'].map(v=>[v,v.replaceAll('_',' ')])],v=>{state.status=v;renderList()});
 select('Departure UTC hour',[['','All hours'],...Array.from({length:24},(_,h)=>[String(h),String(h).padStart(2,'0')+':00–'+String((h+1)%24).padStart(2,'0')+':00 UTC'])],v=>{state.hour=v;renderList()});
 panel.append(filters);
 const otherLabel=element('label',undefined,'observed-overlay');const other=element('input');other.type='checkbox';otherLabel.append(other,document.createTextNode(' Include other local traffic for review'));other.onchange=()=>{state.includeOther=other.checked;renderList()};panel.append(otherLabel);
 const choose=element('select');choose.size=7;choose.setAttribute('aria-label','Observed flight');choose.className='observed-flights';panel.append(choose);
 const time=element('output','—','observed-time');time.setAttribute('aria-live','off');panel.append(time);
 const range=element('input');range.type='range';range.min='0';range.max='86400000';range.step='1000';range.value='0';range.setAttribute('aria-label','Recorded UTC timeline');panel.append(range);
 const transport=element('div',undefined,'observed-transport');const play=element('button','▶ Play'),restart=element('button','↺ Restart'),follow=element('button','Follow selected');
 transport.append(play,restart,follow);panel.append(transport);
 const fit=element('button','Fit active flights');fit.className='observed-fit';panel.append(fit);
 const speed=element('select');speed.setAttribute('aria-label','Recorded playback speed');for(const n of [1,5,20,60]){const o=element('option',n+'× recorded time');o.value=n;if(n===20)o.selected=true;speed.append(o)}panel.append(speed);
 const overlayLabel=element('label',undefined,'observed-overlay');const overlay=element('input');overlay.type='checkbox';overlay.checked=true;overlayLabel.append(overlay,document.createTextNode(' Show candidate reference routes'));panel.append(overlayLabel);
 const detail=element('div',undefined,'observed-detail');detail.setAttribute('aria-live','polite');panel.append(detail);
 panel.append(element('p','Dots: reports · white line: short-gap display interpolation · dashed line: reference. Breaks remain gaps. Altitude offsets are display-only; vertical emphasis does not change measurements.','observed-intro'));
 document.querySelector('.sidebar').append(panel);
 const labels=element('div',undefined,'observed-labels');host.append(labels);
 let lastUI=0,tracking=false;
 for(const input of [choose,range,play,restart,follow,fit,speed,overlay])input.disabled=true;
 const base='/observed-data/';
 async function ensureManifest(){
  if(state.manifest)return;
  try{
   const response=await fetch(base+'manifest.json');if(!response.ok)throw Error('No local observation dataset. Start the A2 local server after processing the sample.');
   const manifest=await response.json();
   if(manifest.schema_version!==1||!Array.isArray(manifest.flights))throw Error('Unsupported observed-data manifest');
   if(manifest.reference_sha256!==data.reference_source_sha256)throw Error('Observed data and procedure reference versions differ. Re-export the local dataset.');
   if(!manifest.flights.length)throw Error('The local processing run contains no reconstructed events.');
   state.manifest=manifest;state.endMs=manifest.end_ms;
   for(const input of [choose,range,play,restart,follow,fit,speed,overlay])input.disabled=false;
   range.min=manifest.start_ms;range.max=manifest.end_ms;
   const eligible=manifest.flights.filter(f=>f.runway_status==='accepted_departure_candidate');
   const pair=eligible.find((f,i)=>eligible.slice(i+1).some(g=>g.runway===f.runway&&g.anchor_ms<f.end_ms-60000&&g.anchor_ms>f.anchor_ms));
   const partner=pair&&eligible.find(g=>g.runway===pair.runway&&g.anchor_ms<pair.end_ms-60000&&g.anchor_ms>pair.anchor_ms);
   state.selected=(pair||eligible[0]||manifest.flights[0])?.flight_id;
   state.timestampMs=(partner||pair||eligible[0]||manifest.flights[0])?.anchor_ms+60000;
   if(!Number.isFinite(state.timestampMs))throw Error('No flights in the local dataset');
   notice.classList.remove('error');notice.textContent=`${manifest.flights.length} reconstructed events · local evaluation sample. Scores are heuristic, not probabilities.`;
   renderList();update(0,performance.now());
  }catch(e){notice.textContent=e.message;notice.classList.add('error')}
 }
 function renderList(){
  choose.replaceChildren();if(!state.manifest)return;
  const listed=state.manifest.flights.filter(f=>included(f)&&(!state.runway||f.runway===state.runway)&&(!state.status||f.match_status===state.status));
  if(!listed.some(f=>f.flight_id===state.selected)){state.selected=listed[0]?.flight_id||null;if(listed[0]){state.timestampMs=Math.min(listed[0].anchor_ms+60000,listed[0].end_ms);state.playing=false}}
  for(const f of listed){const o=element('option',`${utc(f.anchor_ms).slice(0,8)} · ${f.callsign} · ${f.runway||'?'} · ${f.match_status.replaceAll('_',' ')}`);o.value=f.flight_id;o.selected=f.flight_id===state.selected;choose.append(o)}
 }
 const included=f=>(state.includeOther||['accepted_departure_candidate','ambiguous_runway'].includes(f.runway_status))&&(state.hour===''||new Date(f.anchor_ms).getUTCHours()===Number(state.hour));
 function removeGeometry(g){g.traverse(o=>{o.geometry?.dispose();for(const m of [].concat(o.material||[]))m.dispose?.()});group.remove(g)}
 function trackGeometry(payload,color){
  const result=new THREE.Group();
  for(const samples of splitObservedTrack(payload.samples,state.manifest.interpolation_gap_s)){
   // Missing heights split paths too; never bridge an altitude hole.
   let segment=[];const flush=()=>{if(segment.length){const geom=new THREE.BufferGeometry().setFromPoints(segment);result.add(new THREE.Points(geom,new THREE.PointsMaterial({color,size:.035,sizeAttenuation:true})));if(segment.length>1)result.add(new THREE.Line(geom.clone(),new THREE.LineBasicMaterial({color:'#ffffff',transparent:true,opacity:.38})));segment=[]}};
   for(const s of samples){if(s[3]===null&&s[4]===null){flush();continue}const height=(s[3]??s[4])-(s[3]!==null?50:65);segment.push(new THREE.Vector3(s[1],Math.max(0,height)*.0003048*vertical()+.025,s[2]))}flush();
  }
  return result;
 }
 async function loadFlight(summary){
  if(flights.has(summary.flight_id)||pending.has(summary.flight_id)||failed.has(summary.flight_id)||pending.size>=6)return;
  pending.add(summary.flight_id);
  try{
   const response=await fetch(base+summary.url);if(!response.ok)throw Error('Flight file unavailable');const payload=await response.json();
   const color=colors[summary.runway]||colors.unknown,mesh=aircraft(color);mesh.scale.setScalar(.35);group.add(mesh);
   const pin=new THREE.Mesh(new THREE.RingGeometry(.1,.13,24),new THREE.MeshBasicMaterial({color,side:THREE.DoubleSide}));pin.rotation.x=-Math.PI/2;group.add(pin);
   const label=element('span',summary.callsign,'observed-aircraft-label');labels.append(label);
   const trail=trackGeometry(payload,color);group.add(trail);
   const reference=new THREE.Group();
   for(const candidate of payload.match.candidates.slice(0,3)){
    const route=data.routes.find(r=>r.procedure_id===candidate.procedure_id);if(!route)continue;
    const runway=data.runways.find(r=>r.id===route.runway),pts=[new THREE.Vector3(runway.start[0],.035,runway.start[1]),...route.legs.map(l=>{const f=data.fixes[l.fix];return new THREE.Vector3(f.xz[0],.035,f.xz[1])})];
    const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),new THREE.LineDashedMaterial({color,dashSize:.5,gapSize:.3,transparent:true,opacity:.4}));line.computeLineDistances();reference.add(line);
   }group.add(reference);
   flights.set(summary.flight_id,{summary,payload,mesh,pin,label,trail,reference,lastVertical:vertical(),sample:null});
  }catch(e){failed.add(summary.flight_id);state.error=summary.callsign+': '+e.message;notice.textContent=state.error}
  finally{pending.delete(summary.flight_id)}
 }
 function showDetail(item){
  detail.replaceChildren();if(!item)return;
  const {payload,sample}=item;
  detail.append(element('h3',item.summary.callsign+' · '+(item.summary.runway||'uncertain runway')));
  detail.append(element('p',payload.flight.runway_status.replaceAll('_',' ')+' · '+payload.match.status.replaceAll('_',' ')));
  detail.append(element('p',!sample?.available?sample?.reason||'Outside observation window':`${sample.interpolated?'Interpolated display':'Recorded report'} · ${sample.altitudeFt===null?'Altitude unavailable':Math.round(sample.altitudeFt).toLocaleString()+' ft '+sample.altitudeReference} · ${sample.groundSpeedKt===null?'speed unavailable':sample.groundSpeedKt.toFixed(0)+' kt ground speed'}`));
  const list=element('ol');for(const candidate of payload.match.candidates.slice(0,3)){list.append(element('li',`${candidate.procedure_name}: ${candidate.score.toFixed(3)} · median distance ${(candidate.median_distance_m/1000).toFixed(2)} km · ${(candidate.observed_route_coverage*100).toFixed(0)}% reference progress`))}detail.append(list);
  for(const reason of payload.match.reasons)detail.append(element('p',reason));
  detail.append(element('p',`${payload.flight.observation_count} reports · maximum gap ${payload.flight.max_gap_s.toFixed(1)} s · ${payload.flight.missing_altitude_count} without altitude`));
  if(sample?.qualityFlags)detail.append(element('p','Quality: '+sample.qualityFlags));
 }
 function setMode(enabled){state.enabled=enabled;state.playing=false;group.visible=enabled;panel.hidden=!enabled;labels.hidden=!enabled;document.body.classList.toggle('observed-mode-active',enabled);onMode(enabled);if(enabled)ensureManifest()}
 mode.onchange=()=>setMode(mode.value==='observed');
 choose.onchange=()=>{state.selected=choose.value;const f=state.manifest.flights.find(f=>f.flight_id===state.selected);if(f){state.timestampMs=Math.min(f.anchor_ms+60000,f.end_ms);state.playing=false;loadFlight(f);tracking=true}};
 play.onclick=()=>{state.playing=!state.playing};restart.onclick=()=>{state.playing=false;state.timestampMs=state.manifest.flights.find(f=>f.flight_id===state.selected)?.start_ms||state.manifest.start_ms};follow.onclick=()=>tracking=!tracking;
 range.oninput=()=>{state.timestampMs=Number(range.value);state.playing=false};speed.onchange=()=>state.speed=Number(speed.value);
 fit.onclick=()=>{const positions=[...flights.values()].filter(f=>f.mesh.visible).map(f=>f.mesh.position);if(!positions.length)return;tracking=false;const box=new THREE.Box3().setFromPoints(positions),center=box.getCenter(new THREE.Vector3()),size=box.getSize(new THREE.Vector3()),radius=Math.max(size.x,size.z,size.y,5)*1.1/Math.min(camera.aspect,1);controls.target.copy(center);camera.position.copy(center).add(new THREE.Vector3(radius*.35,radius*1.1,radius*.6));controls.update()};
 function update(dt,now){
  if(!state.enabled||!state.manifest)return;
  advanceObserved(state,dt);
  const active=activeFlights(state.manifest.flights,state.timestampMs,state.runway,state.status).filter(included);
  const selected=state.manifest.flights.find(f=>f.flight_id===state.selected);
  const toLoad=[...active.filter(f=>f.flight_id===state.selected),...active.filter(f=>f.flight_id!==state.selected)].slice(0,12);
  if(selected&&!toLoad.some(f=>f.flight_id===selected.flight_id))toLoad.push(selected);
  for(const f of toLoad)loadFlight(f);
  const activeIds=new Set(active.map(f=>f.flight_id));
  // Bound the browser cache while scrubbing a whole day of partitioned flights.
  if(flights.size>24){for(const [id,item] of flights){if(flights.size<=24)break;if(id===state.selected||toLoad.some(f=>f.flight_id===id))continue;for(const g of [item.mesh,item.pin,item.trail,item.reference])removeGeometry(g);item.label.remove();flights.delete(id)}}
  for(const [id,item] of flights){
   if(item.lastVertical!==vertical()){removeGeometry(item.trail);item.trail=trackGeometry(item.payload,colors[item.summary.runway]||colors.unknown);group.add(item.trail);item.lastVertical=vertical()}
   const visible=activeIds.has(id)&&toLoad.some(f=>f.flight_id===id),sample=sampleObserved(item.payload.samples,state.timestampMs,state.manifest.interpolation_gap_s);item.sample=sample;
   const valid=visible&&sample.available;
   item.mesh.visible=valid&&sample.displayAltitudeFt!==null;item.pin.visible=valid;item.label.hidden=!valid;item.trail.visible=id===state.selected;item.reference.visible=overlay.checked&&id===state.selected;
   if(valid){const y=sample.displayAltitudeFt===null?0:Math.max(0,sample.displayAltitudeFt)*.0003048*vertical();item.mesh.position.set(sample.x,y+.035,sample.z);item.mesh.rotation.y=-(sample.trackDeg||0)*Math.PI/180;item.pin.position.set(sample.x,.025,sample.z);item.label.textContent=item.summary.callsign+(sample.displayAltitudeFt===null?' · altitude unavailable':sample.interpolated?' · interpolated':' · report');const v=new THREE.Vector3(sample.x,y+.4,sample.z).project(camera);item.label.hidden=v.z<-1||v.z>1;item.label.style.left=((v.x*.5+.5)*host.clientWidth)+'px';item.label.style.top=((-v.y*.5+.5)*host.clientHeight)+'px'}
  }
  const item=flights.get(state.selected);
  if(tracking&&item?.sample?.available){const s=item.sample,target=new THREE.Vector3(s.x,Math.max(0,s.displayAltitudeFt||0)*.0003048*vertical(),s.z);const offset=camera.position.clone().sub(controls.target);if(offset.length()>20)offset.set(3,5,7);controls.target.lerp(target,.08);camera.position.lerp(target.clone().add(offset),.08)}
  if(now-lastUI>250){time.textContent=utc(state.timestampMs);range.value=state.timestampMs;play.textContent=state.playing?'Ⅱ Pause':'▶ Play';showDetail(item);notice.textContent=state.error||`${active.length} active events (${Math.min(active.length,12)} aircraft shown) · ${state.manifest.flights.length} total · local evaluation`;lastUI=now}
 }
 return {update,setMode,getState:()=>({...state,manifest:undefined,loadedFlights:flights.size,visibleAircraft:[...flights.values()].filter(f=>f.mesh.visible).map(f=>f.summary.flight_id),selectedSample:flights.get(state.selected)?.sample}),selectFlight:id=>{choose.value=id;choose.onchange()},seek:ms=>{state.timestampMs=ms;state.playing=false},setPlaying:value=>state.playing=Boolean(value)};
}
