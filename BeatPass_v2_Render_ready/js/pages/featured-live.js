// FLUJO: destacados.html -> api.publicEvents() -> events.py -> organismo event-card.js.
(function(global){
'use strict';
async function init(){
  const app=global.BeatPass,section=document.getElementById('published-events');if(!section)return;
  try{
    const events=await app.api.publicEvents({limit:6});
    section.hidden=!events.length;if(!events.length)return;
    const grid=document.getElementById('published-events-grid');
    grid.replaceChildren(...events.map(item=>app.eventCard(item)));
  }catch(_error){section.hidden=true;}
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>void init());else void init();
})(window);
