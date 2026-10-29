import * as THREE from 'three';
import {OrbitControls} from './vendor/OrbitControls.js';
import {buildFlight,sampleFlight,advance,constraintLabel} from './flight-model.mjs';
import {mountObserved} from './observed-layer.mjs';
import {mountNoise} from './noise-layer.mjs';

const $=id=>document.getElementById(id),host=$('canvas-host'),viewport=$('viewport');
let data,scene,camera,renderer,controls,selected='34C',vertical=4,speed=1,cameraMode='airport',last=0,ready=false;
let observed=null;
let focusAngle=0,focusSubject="aircraft",customTitle="",customCopy="";
const reducedMotion=matchMedia("(prefers-reduced-motion: reduce)").matches;
const states={},worldLabels=[],pickables=[],clock=new THREE.Clock(),raycaster=new THREE.Raycaster();
const toV=(p,alt=0)=>new THREE.Vector3(p[0],alt*.0003048*vertical,p[1]);
const zero=new THREE.Vector3(),tempV=new THREE.Vector3();
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const timeLabel=t=>`${Math.floor(t/60).toString().padStart(2,'0')}:${Math.floor(t%60).toString().padStart(2,'0')}`;
function chaseCamera(s,dt){
 const segment=s.flight.segments[s.sample.index],plane=s.plane.position,next=toV(segment.b.xz,segment.b.altFt);
 const forward=new THREE.Vector3(next.x-plane.x,0,next.z-plane.z);
 if(forward.lengthSq()<.0001)forward.set(-Math.sin(s.sample.heading),0,-Math.cos(s.sample.heading));
 const remaining=forward.length();forward.normalize();
 const distance=clamp(segment.distance*.42,2.8,18);
 const ahead=Math.min(remaining*.38,distance*.55);
 const target=plane.clone().addScaledVector(forward,ahead);
 target.y+=Math.min(Math.max(next.y-plane.y,0)*.2,distance*.18);
 const side=new THREE.Vector3(-forward.z,0,forward.x);
 const position=plane.clone().addScaledVector(forward,-distance).addScaledVector(side,distance*.22);
 position.y+=Math.max(1.3,distance*.52);
 const ease=1-Math.exp(-dt*2.6);
 controls.target.lerp(target,ease);camera.position.lerp(position,ease);
}
function geom(positions){const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));g.computeVertexNormals();return g}
function line(points,color,opacity=1){return new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineBasicMaterial({color,transparent:true,opacity}))}
function label(text,position,type,color){const el=document.createElement('div');el.className='world-label '+type;el.textContent=text;if(color)el.style.setProperty('--label-color',color);$('labels').append(el);const item={el,position,type};worldLabels.push(item);return item}
function disposeGroup(group){group.traverse(o=>{o.geometry?.dispose();if(o.material){for(const m of [].concat(o.material))m.dispose()}});scene.remove(group)}

function buildGround(){
 const styles={airport_boundary:['#9eb8c6',.002],land_use:['#a8c2d0',.001],water:['#7daec7',.003],green_spaces:['#b5d8c4',.004],buildings:['#e6e4dc',.012],roads:['#eaf3f5',.004],railway:['#d6e4e9',.005],taxiways:['#cddade',.007],aprons_and_stopways:['#b9cbd2',.005],terminals_and_hangars:['#f1eee5',.02],coastline:['#dceaf0',.007]};
 const batches={};
 for(const feature of data.ground){
  if(feature.layer==='runway_surfaces')continue;
  const key=feature.layer;if(!styles[key])continue;
  const batch=batches[key]??={triangles:[],lines:[]},height=styles[key][1];
  if(feature.kind==='line'){
   const pts=feature.coords;for(let i=1;i<pts.length;i++)batch.lines.push(pts[i-1][0],height,pts[i-1][1],pts[i][0],height,pts[i][1]);
  }else{
   const rings=feature.coords.map(r=>r.slice(0,-1).map(p=>new THREE.Vector2(p[0],p[1]))).filter(r=>r.length>2);if(!rings.length)continue;
   const vertices=rings.flat(),triangles=THREE.ShapeUtils.triangulateShape(rings[0],rings.slice(1));
   for(const tri of triangles)for(const idx of tri){const p=vertices[idx];batch.triangles.push(p.x,height,p.y)}
   if(key==='buildings'||key==='terminals_and_hangars')for(const ring of rings)for(let i=0;i<ring.length;i++){const a=ring[i],b=ring[(i+1)%ring.length];batch.triangles.push(a.x,0,a.y,b.x,0,b.y,b.x,height,b.y,a.x,0,a.y,b.x,height,b.y,a.x,height,a.y)}
  }
 }
 const base=new THREE.Mesh(new THREE.PlaneGeometry(500,500),new THREE.MeshStandardMaterial({color:'#adc8d7',roughness:1}));base.rotation.x=-Math.PI/2;base.position.y=-.002;scene.add(base);
 
 for(const [key,b] of Object.entries(batches)){
  const color=styles[key][0];if(b.triangles.length){const m=new THREE.Mesh(geom(b.triangles),new THREE.MeshStandardMaterial({color,side:THREE.DoubleSide,roughness:1}));scene.add(m)}
  if(b.lines.length)scene.add(new THREE.LineSegments(geom(b.lines),new THREE.LineBasicMaterial({color,transparent:true,opacity:key==='roads'?.7:1})));
 }
}
function aircraft(color){
 const group=new THREE.Group(),white=new THREE.MeshStandardMaterial({color:'#e0edf2',metalness:.25,roughness:.38}),paint=new THREE.MeshStandardMaterial({color,metalness:.2,roughness:.4}),dark=new THREE.MeshStandardMaterial({color:'#19313d',metalness:.3,roughness:.3});
 const body=new THREE.Mesh(new THREE.CapsuleGeometry(.105,1.05,8,16),white);body.rotation.x=Math.PI/2;group.add(body);
 const nose=new THREE.Mesh(new THREE.SphereGeometry(.105,16,12),white);nose.scale.set(1,1,1.6);nose.position.z=-.57;group.add(nose);
 const cockpit=new THREE.Mesh(new THREE.SphereGeometry(.075,12,8),dark);cockpit.scale.set(1,.4,1);cockpit.position.set(0,.078,-.52);group.add(cockpit);
 function wing(points,mat){const vs=points.map(p=>new THREE.Vector2(...p)),tri=THREE.ShapeUtils.triangulateShape(vs,[]),pos=[];for(const t of tri)for(const i of t)pos.push(vs[i].x,0,vs[i].y);const mesh=new THREE.Mesh(geom(pos),mat);mesh.material.side=THREE.DoubleSide;group.add(mesh)}
 wing([[-.06,-.18],[-.68,.17],[-.67,.28],[-.09,.16],[.09,.16],[.67,.28],[.68,.17],[.06,-.18]],white);
 wing([[-.05,.41],[-.30,.60],[-.28,.66],[.28,.66],[.30,.60],[.05,.41]],paint);
 const fin=new THREE.Mesh(geom([0,0,.38,0,.30,.62,0,0,.67]),paint);fin.material.side=THREE.DoubleSide;group.add(fin);
 for(const x of [-.30,.30]){const engine=new THREE.Mesh(new THREE.CylinderGeometry(.06,.055,.23,12),white);engine.rotation.x=Math.PI/2;engine.position.set(x,-.065,.03);group.add(engine);const intake=new THREE.Mesh(new THREE.CircleGeometry(.045,12),dark);intake.rotation.y=Math.PI;intake.position.set(x,-.065,-.087);group.add(intake)}
 for(const x of [-.67,.67]){const light=new THREE.Mesh(new THREE.SphereGeometry(.025,8,6),new THREE.MeshBasicMaterial({color:x<0?'#ff6887':'#72ffc7'}));light.position.set(x,.015,.25);group.add(light)}
 return group;
}
function buildRunways(){
 for(const runway of data.runways){
  const start=toV(runway.start),finish=toV(runway.finish),mid=start.clone().add(finish).multiplyScalar(.5),heading=Math.atan2(-(finish.x-start.x),-(finish.z-start.z));
  const group=new THREE.Group();group.position.copy(mid);group.rotation.y=heading;
  const surface=new THREE.Mesh(new THREE.BoxGeometry(.06,.008,runway.lengthKm),new THREE.MeshStandardMaterial({color:runway.color,emissive:runway.color,emissiveIntensity:.12,roughness:.7}));surface.position.y=.008;surface.userData={name:`RWY ${runway.id} / ${runway.end}`,detail:'Published thresholds · approximate 60 m width'};pickables.push(surface);group.add(surface);
  const stripeMat=new THREE.MeshBasicMaterial({color:'#e7f4f5'});
  for(let z=-runway.lengthKm/2+.10;z<runway.lengthKm/2-.10;z+=.12){const stripe=new THREE.Mesh(new THREE.PlaneGeometry(.003,.055),stripeMat);stripe.rotation.x=-Math.PI/2;stripe.position.set(0,.013,z);group.add(stripe)}
  for(const z of [-runway.lengthKm/2+.07,runway.lengthKm/2-.07])for(let x=-.024;x<=.024;x+=.008){const mark=new THREE.Mesh(new THREE.PlaneGeometry(.004,.04),stripeMat);mark.rotation.x=-Math.PI/2;mark.position.set(x,.014,z);group.add(mark)}
  scene.add(group);
  const plane=aircraft(runway.color);plane.position.copy(start).add(new THREE.Vector3(0,.04,0));plane.rotation.y=heading;plane.scale.setScalar(.14);scene.add(plane);
  const ring=new THREE.Mesh(new THREE.RingGeometry(.09,.105,48),new THREE.MeshBasicMaterial({color:runway.color,transparent:true,opacity:.45,side:THREE.DoubleSide}));ring.rotation.x=-Math.PI/2;ring.position.copy(start);ring.position.y=.017;scene.add(ring);
  const planeLabel=label(`✈ ${runway.id} · READY`,plane.position.clone(),'aircraft',runway.color);
  label(runway.end,finish.clone().add(new THREE.Vector3(0,.06,0)),'runway',runway.color);
  states[runway.id]={runway,plane,ring,planeLabel,flight:null,playing:false,elapsed:0,loops:0,loop:true,routeGroup:null,routeLabels:[],sample:null};
 }
}
function buildRouteVisual(s){
 if(s.routeGroup)disposeGroup(s.routeGroup);
 for(const l of s.routeLabels){l.el.remove();const i=worldLabels.indexOf(l);if(i>=0)worldLabels.splice(i,1)}s.routeLabels=[];
 for(let i=pickables.length-1;i>=0;i--)if(pickables[i].userData.owner===s.runway.id)pickables.splice(i,1);
 if(!s.flight)return;
 const group=new THREE.Group();s.routeGroup=group;const pts=s.flight.points.map(p=>toV(p.xz,p.altFt));
 const ref=line(pts,s.runway.color,.88);group.add(ref);
 const groundLine=line(pts.map(p=>new THREE.Vector3(p.x,.015,p.z)),s.runway.color,.32);group.add(groundLine);
 s.trail=line([pts[0],pts[0]],s.runway.color,1);group.add(s.trail);
 for(let i=0;i<pts.length;i++){
  const p=s.flight.points[i],point=pts[i],radius=i<3?.045:.12;
  const pin=new THREE.Mesh(new THREE.OctahedronGeometry(radius),new THREE.MeshBasicMaterial({color:s.runway.color,transparent:true,opacity:.95}));pin.position.copy(point);pin.userData={owner:s.runway.id,name:p.name,detail:p.kind==='published fix'?`${p.path} · ${constraintLabel(p.altitude)}${p.speed?' · max '+p.speed.slice(1)+' kt':''}`:'Illustrative ground / take-off animation point'};pickables.push(pin);group.add(pin);
  if(i>2){group.add(line([new THREE.Vector3(point.x,.02,point.z),point],s.runway.color,.14));s.routeLabels.push(label(p.name,point.clone().add(new THREE.Vector3(0,.18,0)),'fix',s.runway.color))}
 }
 scene.add(group);
}
function setCameraMode(mode){
 cameraMode=mode;document.body.classList.toggle('focus-mode',mode==='focus');$('focus').classList.toggle('active',mode==='focus');$('focus').setAttribute('aria-pressed',String(mode==='focus'));for(const [id,value] of [['airport','airport'],['route-view','route'],['follow','follow'],['top-view','top']])$(id).classList.toggle('active',mode===value);
 $('camera-mode').textContent=mode==='free'?'FREE CAMERA':mode.toUpperCase()+' VIEW';
 if(mode==='focus'){focusAngle=0;controls.enableDamping=false;updateFocusCaption()}else{controls.enableDamping=true}
 if(mode==='airport'){controls.target.set(0,0,0);camera.position.set(7,8.2,10);controls.update()}
 if(mode==='route'){
  const s=states[selected];if(!s.flight){setCameraMode('airport');return}
  const bounds=new THREE.Box3().setFromPoints(s.flight.points.map(p=>toV(p.xz,p.altFt))),center=bounds.getCenter(new THREE.Vector3()),size=bounds.getSize(new THREE.Vector3()),radius=Math.max(size.x,size.z,size.y,12)*1.15/Math.min(1,camera.aspect);
  controls.target.copy(center);camera.position.copy(center).add(new THREE.Vector3(radius*.65,radius*.85,radius));controls.update();
 }
 if(mode==='top'){controls.target.set(0,0,0);camera.position.set(0,18,.001);controls.update()}
}
function selectRunway(id){selected=id;document.documentElement.style.setProperty('--accent',states[id].runway.color);renderSidebar();updateSelected();if(cameraMode==='follow'&&!states[id].flight)setCameraMode('airport')}
function chooseProcedure(route){
 const s=states[route.runway];s.flight=buildFlight(route,s.runway,data.fixes);s.elapsed=0;s.loops=0;s.playing=false;s.sample=sampleFlight(s.flight,0);s.plane.position.copy(toV(s.runway.start));buildRouteVisual(s);selectRunway(route.runway);if(cameraMode==='route')setCameraMode('route');updateUI();
}
function renderSidebar(){
 $('runways').replaceChildren();for(const id of ['34L','34C','34R']){const b=document.createElement('button');b.className='runway-tab'+(selected===id?' active':'');b.textContent=id;b.style.setProperty('--runway',states[id].runway.color);b.setAttribute('role','tab');b.setAttribute('aria-selected',String(selected===id));b.onclick=()=>selectRunway(id);$('runways').append(b)}
 $('procedures').replaceChildren();for(const route of data.routes.filter(r=>r.runway===selected)){
  const b=document.createElement('button');b.className='procedure'+(states[selected].flight?.route.id===route.id?' active':'');b.setAttribute('aria-label',`Start ${route.name} from ${route.runway}`);
  const arrow=document.createElement('span');arrow.className='arrow';arrow.textContent='↗';const copy=document.createElement('span');copy.className='copy';const title=document.createElement('b');title.textContent=route.name;const sub=document.createElement('small');sub.textContent=`${route.legs.length} published fixes · ${route.legs.at(-1).fix}`;copy.append(title,sub);const tag=document.createElement('span');tag.className='tag';tag.textContent=route.warning?'⚑':'▶';if(route.warning){tag.classList.add('warning-dot');b.title=route.warning}b.append(arrow,copy,tag);b.onclick=()=>chooseProcedure(route);$('procedures').append(b);
 }
 $('fleet').replaceChildren();for(const id of ['34L','34C','34R']){const row=document.createElement('div');row.className='fleet-row';row.style.setProperty('--runway',states[id].runway.color);const dot=document.createElement('i'),name=document.createElement('b'),status=document.createElement('span');name.textContent=id;status.id='fleet-'+id;row.append(dot,name,status);$('fleet').append(row)}
}
function updateSelected(){
 const s=states[selected];$('flight-id').textContent='AIRCRAFT '+selected;$('loop').checked=s.loop;
 $('runway-caption').textContent='OEJN / RUNWAY '+selected;$('route-caption').textContent=s.flight?s.flight.route.name:'Ready for departure.';
 $('route-description').textContent=s.flight?(s.flight.route.warning?'⚑ Source issue retained — see Sources & assumptions.':`${s.flight.route.legs.length} published fixes · AIP AMDT 10/26 · illustrative climb and timing`):'Choose a procedure to begin this aircraft’s departure.';
}
function updateFocusCaption(){
 const s=states[selected],route=s.flight?.route;
 $('focus-eyebrow').textContent=`OEJN / RUNWAY ${selected} / ${focusSubject==='airport'?'AIRPORT ORBIT':'AIRCRAFT ORBIT'}`;
 $('focus-title').textContent=customTitle||(route?route.name:'The next horizon.');
 $('focus-copy').textContent=customCopy||(route?`From Jeddah to ${route.legs.at(-1).fix}. A departure, seen from a new perspective.`:'Three runways. One gateway to the sky.');
 $('focus-progress').textContent=route?`${s.playing?'IN MOTION':'PAUSED'}  /  NEXT ${s.sample?.next||'—'}  /  ${Math.round(s.sample?.altFt||0).toLocaleString()} FT · DEMO`:'SELECT A PROCEDURE TO BEGIN · EXPLORATION VIEW';
}
function renderProfile(s,sample){
 if(!s.flight){$('profile').replaceChildren();return}
 const max=Math.max(...s.flight.points.map(p=>p.altFt),1000),pts=s.flight.points.map((p,i)=>[i===0?0:s.flight.segments[i-1].end/s.flight.duration*300,63-p.altFt/max*55]);
 const path='M'+pts.map(p=>p.join(',')).join('L');const x=clamp(s.elapsed/s.flight.duration,0,1)*300,y=63-sample.altFt/max*55;
 $('profile').innerHTML=`<path d="M0 64H300" stroke="#294759"/><path d="${path}L300 64H0Z" fill="${s.runway.color}" opacity=".07"/><path d="${path}" fill="none" stroke="${s.runway.color}" stroke-width="1.5"/><circle cx="${x}" cy="${y}" r="3" fill="${s.runway.color}"/>`;
}
function updateUI(){
 if(cameraMode==='focus')updateFocusCaption();
 for(const [id,s] of Object.entries(states))$('fleet-'+id).textContent=s.flight?`${s.flight.route.name} · ${s.playing?'playing':'paused'}`:'At runway · ready';
 const s=states[selected],sample=s.sample;
 $('play').textContent=s.playing?'Ⅱ Pause':'▶ Play';$('duration').textContent=s.flight?timeLabel(s.flight.duration)+' demo time':'Select a procedure';$('elapsed').textContent=timeLabel(Math.min(s.elapsed,s.flight?.duration||0));$('scrub').value=s.flight?clamp(s.elapsed/s.flight.duration,0,1)*1000:0;
 $('altitude').innerHTML=Math.round(sample?.altFt||0).toLocaleString()+' <em>ft</em>';$('next-point').textContent=sample?.next||'—';$('phase').textContent=!s.flight?'PARKED':sample.complete?(s.loop?'RESTARTING':'COMPLETE'):!s.playing?'PAUSED':sample.ground?'GROUND ROLL':'AIRBORNE';$('fix-progress').textContent=s.flight?`${sample.complete?s.flight.route.legs.length:Math.max(0,(sample?.index||0)-2)} / ${s.flight.route.legs.length} fixes passed`:'Select a departure';$('loop-count').textContent='Loop '+s.loops;renderProfile(s,sample);
}
function animate(now){
 requestAnimationFrame(animate);const dt=Math.min(clock.getDelta(),.1);if(!ready)return;
 for(const s of Object.values(states)){
  if(s.flight){advance(s,dt*speed);const sample=sampleFlight(s.flight,s.elapsed);s.sample=sample;
   const pos=new THREE.Vector3(sample.x,sample.altFt*.0003048*vertical+.035,sample.z);s.plane.position.copy(pos);s.plane.rotation.y=sample.heading;
   const segment=s.flight.segments[sample.index],slope=Math.atan2((segment.b.altFt-segment.a.altFt)*.0003048,segment.distance);s.plane.rotation.x=clamp(slope,0,.2);
   s.ring.position.set(pos.x,.018,pos.z);s.ring.material.opacity=sample.ground?.45:.16;
   const points=s.flight.points.slice(0,sample.index+1).map(p=>toV(p.xz,p.altFt));points.push(pos);s.trail.geometry.dispose();s.trail.geometry=new THREE.BufferGeometry().setFromPoints(points);
   s.planeLabel.el.textContent=`✈ ${s.runway.id} · ${s.flight.route.name}`;
  }
  const distance=camera.position.distanceTo(s.plane.position);s.plane.scale.setScalar(clamp(distance*.032,.25,4));s.planeLabel.position.copy(s.plane.position).add(new THREE.Vector3(0,clamp(distance*.033,.25,5),0));
  s.planeLabel.el.style.opacity=s.runway.id===selected?'1':'.75';
 }
 if(cameraMode==='follow'){
  const s=states[selected];if(s.flight)chaseCamera(s,dt);
 }
 if(cameraMode==='focus'){
  const s=states[selected];
  if(focusSubject==='aircraft'&&s.flight&&s.playing&&!s.sample.ground)chaseCamera(s,dt);
  else{
   const target=focusSubject==='airport'?zero:s.plane.position;
   if(!reducedMotion)focusAngle+=dt*.065;
   const radius=focusSubject==='airport'?10:2.25,elevation=focusSubject==='airport'?6:1.05;
   const offset=new THREE.Vector3(Math.sin(focusAngle+.7)*radius,elevation,Math.cos(focusAngle+.7)*radius);
   const ease=reducedMotion?1:1-Math.exp(-dt*2.5);
   controls.target.lerp(target,ease);camera.position.lerp(target.clone().add(offset),ease);
  }
 }
 observed?.update(dt,now);controls.update();renderer.render(scene,camera);
 const width=host.clientWidth,height=host.clientHeight;
 for(const l of worldLabels){tempV.copy(l.position).project(camera);const selectedFlight=states[selected],focusVisible=l===selectedFlight.planeLabel||(l.type==='fix'&&l.el.textContent===selectedFlight.sample?.next);const focusHidden=cameraMode==='focus'&&!focusVisible;const show=!focusHidden&&tempV.z>=-1&&tempV.z<=1&&Math.abs(tempV.x)<1.05&&Math.abs(tempV.y)<1.05;l.el.style.display=show?'':'none';if(show){l.el.style.left=((tempV.x*.5+.5)*width)+'px';l.el.style.top=((-tempV.y*.5+.5)*height)+'px'}}
 if(now-last>100){updateUI();last=now}
}
function wireControls(){
 $('focus').onclick=()=>setCameraMode('focus');$('exit-focus').onclick=()=>setCameraMode('airport');
 $('focus-subject').onchange=e=>{focusSubject=e.target.value;focusAngle=0;updateFocusCaption()};
 $('edit-caption').onclick=()=>{$('caption-title-input').value=customTitle;$('caption-copy-input').value=customCopy;$('caption-dialog').showModal()};
 $('close-caption').onclick=()=>$('caption-dialog').close();
 $('save-caption').onclick=()=>{customTitle=$('caption-title-input').value.trim();customCopy=$('caption-copy-input').value.trim();updateFocusCaption();$('caption-dialog').close()};
 $('reset-caption').onclick=()=>{customTitle='';customCopy='';updateFocusCaption();$('caption-dialog').close()};
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&cameraMode==='focus'&&!$('caption-dialog').open&&!$('source-dialog').open)setCameraMode('airport')});
 $('airport').onclick=()=>setCameraMode('airport');$('route-view').onclick=()=>setCameraMode('route');$('follow').onclick=()=>setCameraMode('follow');$('top-view').onclick=()=>setCameraMode('top');
 $('play').onclick=()=>{let s=states[selected];if(!s.flight){chooseProcedure(data.routes.find(r=>r.runway===selected));s=states[selected]}if(s.elapsed>=s.flight.duration)s.elapsed=0;s.playing=!s.playing;if(s.playing)setCameraMode('follow');updateUI()};
 $('restart').onclick=()=>{const s=states[selected];s.elapsed=0;s.loops=0;s.playing=false;if(s.flight)s.sample=sampleFlight(s.flight,0);updateUI()};
 $('pause-all').onclick=()=>{for(const s of Object.values(states))s.playing=false;updateUI()};
 $('speed').onchange=e=>speed=Number(e.target.value);$('loop').onchange=e=>states[selected].loop=e.target.checked;
 $('scrub').oninput=e=>{const s=states[selected];if(s.flight){s.elapsed=Number(e.target.value)/1000*s.flight.duration;s.playing=false}};
 $('height').oninput=e=>{vertical=Number(e.target.value);$('height-label').textContent=vertical+'×';for(const s of Object.values(states))if(s.flight)buildRouteVisual(s);if(cameraMode==='route')setCameraMode('route')};
 $('sources').onclick=()=>$('source-dialog').showModal();$('close-sources').onclick=()=>$('source-dialog').close();
 for(const rw of ['34C','34L','34R'])for(const n of [1,2]){const a=document.createElement('a');a.href=`https://github.com/M-AlGhazali/Research-and-Innovation-department-SANS-project/blob/main/sources/map-2/${rw}-table-${n}.pdf`;a.target='_blank';a.rel='noopener';a.textContent=`${rw} · source ${n}`;$('source-links').append(a)}
 const observer=new ResizeObserver(()=>{const w=host.clientWidth,h=host.clientHeight;renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix()});observer.observe(host);
 controls.addEventListener('start',()=>{if(cameraMode==='follow'||cameraMode==='focus')setCameraMode('free')});
 renderer.domElement.addEventListener('pointermove',e=>{
  if(e.buttons){$('tooltip').style.display='none';return}const rect=renderer.domElement.getBoundingClientRect();raycaster.setFromCamera(new THREE.Vector2((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1),camera);const hit=raycaster.intersectObjects(pickables,false)[0];if(!hit){$('tooltip').style.display='none';return}
  const info=hit.object.userData;$('tooltip').replaceChildren();const title=document.createElement('b'),body=document.createElement('span');title.textContent=info.name;body.textContent=info.detail;$('tooltip').append(title,body);$('tooltip').style.display='block';$('tooltip').style.left=Math.min(e.clientX-rect.left+15,rect.width-310)+'px';$('tooltip').style.top=Math.min(e.clientY-rect.top+15,rect.height-130)+'px';
 });renderer.domElement.addEventListener('pointerleave',()=>$('tooltip').style.display='none');
}
async function init(){
 try{
  const response=await fetch('./data.json');if(!response.ok)throw new Error('Map dataset could not be loaded');data=await response.json();
  const runwayColors={'34C':'#168d9b','34L':'#bb4b76','34R':'#aa7519'};
  for(const runway of data.runways)runway.color=runwayColors[runway.id]||runway.color;
  scene=new THREE.Scene();scene.background=new THREE.Color('#adc8d7');scene.fog=new THREE.FogExp2('#adc8d7',.003);
  camera=new THREE.PerspectiveCamera(46,1,.005,1000);renderer=new THREE.WebGLRenderer({antialias:true,alpha:false});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.05;renderer.setSize(host.clientWidth,host.clientHeight);host.append(renderer.domElement);
  controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.dampingFactor=.08;controls.maxPolarAngle=Math.PI/2-.025;controls.minDistance=.8;controls.maxDistance=350;
  scene.add(new THREE.HemisphereLight('#ffffff','#6c8590',2.0));const light=new THREE.DirectionalLight('#fff5e6',2.4);light.position.set(-10,25,10);scene.add(light);
  buildGround();buildRunways();wireControls();selectRunway('34C');setCameraMode('airport');
   observed=mountObserved({scene,data,aircraft,host,vertical:()=>vertical,camera,controls,onMode:enabled=>{document.querySelector('.attribution').textContent=enabled?'© OpenStreetMap contributors · Wingbits recorded reports · geometric candidates, clearance unknown':'© OpenStreetMap contributors · SANS AIP AMDT 10/26 · Concept playback, not recorded flights';for(const s of Object.values(states)){s.playing=false;s.plane.visible=!enabled;s.ring.visible=!enabled;s.planeLabel.el.hidden=enabled;if(s.routeGroup)s.routeGroup.visible=!enabled;for(const l of s.routeLabels)l.el.hidden=enabled}setCameraMode('airport');$('sources').textContent=enabled?'Sources & interpretation':'Sources & assumptions'}});$('loading').style.display='none';ready=true;try{const nr=await fetch('./noise-layer.json');if(nr.ok)window.map2noise=mountNoise({scene,data,viewport,noise:await nr.json()})}catch(err){console.warn('noise layer',err)}
  window.map2={observed,getState:()=>Object.fromEntries(Object.entries(states).map(([id,s])=>[id,{procedure:s.flight?.route.name||null,playing:s.playing,elapsed:s.elapsed,duration:s.flight?.duration||0,loops:s.loops,next:s.sample?.next,position:s.plane.position.toArray()}])),getCamera:()=>({mode:cameraMode,subject:focusSubject,position:camera.position.toArray(),target:controls.target.toArray()}),getCounts:()=>({aircraft:Object.keys(states).length,procedures:data.routes.length,fixes:Object.keys(data.fixes).length}),selectProcedure:name=>{const route=data.routes.find(r=>r.name===name);if(!route)throw new Error('Unknown procedure');chooseProcedure(route)}};
  requestAnimationFrame(animate);
 }catch(error){$('loading').classList.add('error');$('loading').textContent='Unable to open the 3D scene. Use “Start Map 2.cmd” and a browser with WebGL enabled. '+error.message;console.error(error)}
}
init();
