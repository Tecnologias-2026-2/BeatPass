// FLUJO: reviews.html -> api.js -> main.py/events.py -> AuditLog.
(function(global){
 'use strict';
 const api=global.BeatPass.api;
 const make=(tag,text,cls)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=String(text);if(cls)node.className=cls;return node;};
 async function renderSection(kind,root,status){
  root.replaceChildren();status.textContent='Consultando rechazados...';
  try{
   const rows=kind==='account'?await api.rejectedApplications():await api.rejectedEventReviews();
   status.textContent=rows.length?`${rows.length} registro(s) rechazado(s).`:'No hay rechazos en esta sección.';
   for(const item of rows){
    const card=make('article',undefined,'bp-review-card');
    card.append(make('h3',kind==='account'?item.organization:item.title),
      make('p',kind==='account'?`${item.fullname} · ${item.email} · ${item.city}`:
        `${item.organizer_name} · ${item.organizer_email} · ${item.date} · ${item.city}`),
      make('p',`Motivo del rechazo: ${item.reason||item.review_reason||'No indicado.'}`));
    if(kind==='account'&&!item.email_verified){
     card.append(make('p','Correo sin verificar: revisa la identidad antes de aprobar.','bp-review-warning'));
    }
    if(kind==='event'){
     card.append(make('p',item.description));
     if(item.hasCover){
      const preview=make('img',undefined,'bp-review-cover');preview.alt=`Portada de ${item.title}`;
      card.prepend(preview);
      api.eventRevisionCover(item.revision_id).then(blob=>{
       const url=URL.createObjectURL(blob);preview.src=url;
       preview.addEventListener('load',()=>URL.revokeObjectURL(url),{once:true});
       preview.addEventListener('error',()=>URL.revokeObjectURL(url),{once:true});
      }).catch(()=>preview.remove());
     }
    }
    const restore=make('button','Volver a pendientes','bp-button bp-button--primary');restore.type='button';
    restore.addEventListener('click',async()=>{
     if(!global.confirm('¿Recuperar este rechazo? Pasará a Pendientes y necesitará nueva aprobación.'))return;
     restore.disabled=true;
     try{
      const result=kind==='account'?await api.restoreRejectedApplication(item.id):
          await api.restoreRejectedEvent(item.revision_id);
      status.textContent=result.message;
      // Actualiza también la bandeja Pendientes al recargar, sin aceptar por accidente.
      global.location.reload();
     }catch(error){status.textContent=error.message;restore.disabled=false;}
    });
    card.append(restore);root.append(card);
   }
  }catch(error){status.textContent=error.message||'No se pudo cargar la lista.';}
 }
 async function init(){
  const accounts=document.getElementById('review-rejected-applications');
  const events=document.getElementById('review-rejected-events');
  if(!accounts||!events)return;
  const as=document.getElementById('review-rejected-applications-status');
  const es=document.getElementById('review-rejected-events-status');
  try{
   const me=await api.me();if(!me.roles.includes('administracion'))throw new Error('Acceso restringido a administración.');
   document.getElementById('rechazados').hidden=false;
   await Promise.all([renderSection('account',accounts,as),renderSection('event',events,es)]);
  }catch(error){as.textContent=es.textContent=error.message;}
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>void init());else void init();
})(window);
