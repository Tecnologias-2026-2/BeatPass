// FLUJO: reviews.html -> api.js -> backend/events.py para aprobar/rechazar eventos.
/** Bandeja administrativa de revisiones de eventos, independiente de solicitudes de cuenta. */
(function(global){
'use strict';
async function init(){
 const api=global.BeatPass.api,root=document.getElementById('review-events'),status=document.getElementById('review-events-status');
 if(!root||!status)return;
 const element=(tag,text,cls='')=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=String(text);if(cls)node.className=cls;return node;};
 async function refresh(){
  status.textContent='Consultando eventos pendientes...';root.replaceChildren();
  try{
   const me=await api.me();if(!me.roles.includes('administracion'))throw new Error('Solo administración puede revisar eventos.');
   const rows=await api.pendingEventReviews();
   status.textContent=rows.length?`${rows.length} propuesta(s) pendientes de aprobación.`:'No hay eventos pendientes.';
   rows.forEach(item=>{
    const card=element('article',undefined,'bp-review-card');
    if(item.hasCover){
     const cover=document.createElement('img');cover.alt=`Portada propuesta para ${item.title}`;
     cover.className='bp-review-cover';cover.loading='lazy';card.append(cover);
     api.eventRevisionCover(item.revision_id).then(blob=>{
       const url=URL.createObjectURL(blob);cover.src=url;
       cover.addEventListener('load',()=>URL.revokeObjectURL(url),{once:true});
       cover.addEventListener('error',()=>URL.revokeObjectURL(url),{once:true});
     }).catch(()=>{cover.remove();});
    }
    card.append(element('h3',item.title),element('p',`${item.organizer_name} · ${item.organizer_email}`),
      element('p',`${item.category} · ${item.date} ${item.time} (${item.timezone}) · ${item.venue}, ${item.city}`),
      element('p',item.short),element('p',item.description),
      element('p',`Zonas: ${item.ticketTypes.map(x=>`${x.name}: $${Number(x.price).toLocaleString('es-CO')} · ${Number(x.capacity || 0)} cupos`).join(' · ')}`));
    const label=element('label','Motivo de revisión (obligatorio para rechazar)'),reason=element('textarea',undefined,'bp-input');
    reason.maxLength=500;reason.rows=2;label.append(reason);
    const actions=element('div',undefined,'bp-review-actions');
    const approve=element('button','Aprobar y publicar','bp-button bp-button--primary');approve.type='button';
    const reject=element('button','Rechazar y devolver','bp-review-reject');reject.type='button';
    async function decide(action){
     if(action==='reject'&&!reason.value.trim()){status.textContent='Indica el motivo para rechazar.';reason.focus();return;}
     if(!global.confirm(action==='approve'?`¿Publicar «${item.title}» en el catálogo?`:`¿Devolver «${item.title}» al organizador?`))return;
     approve.disabled=reject.disabled=true;
     try{const result=await api.reviewEvent(item.revision_id,action,reason.value.trim());status.textContent=result.message;await refresh();}
     catch(error){status.textContent=error.message;approve.disabled=reject.disabled=false;}
    }
    approve.addEventListener('click',()=>void decide('approve'));reject.addEventListener('click',()=>void decide('reject'));
    actions.append(approve,reject);card.append(label,actions);root.append(card);
   });
  }catch(error){status.textContent=error.message||'No se pudo revisar la bandeja.';}
 }
 await refresh();
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>void init());else void init();
})(window);
