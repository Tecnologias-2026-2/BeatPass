// FLUJO: dashboard.html recoge datos -> api.js -> backend/events.py -> event_models.py.
/** Editor REAL 2B. Los borradores y fotografías se guardan en FastAPI/SQLite.
 *  Ninguna operación de este archivo puede saltarse la revisión administrativa.
 */
(function(global){
'use strict';
const app=global.BeatPass, api=app.api, coverTools=global.BeatPassCoverImages;
const $=id=>document.getElementById(id);
const element=(tag,cls,txt)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(txt!==undefined)n.textContent=txt;return n;};
async function init(){
 const form=$('admin-event-form');if(!form)return;
 const priceRoot=$('admin-price-rows'),notice=$('admin-status'),coverInput=$('event-cover-file'),previewImage=$('preview-image');
 let events=[], activeId=null, coverBlob=null, coverUrl=null, removeCover=false, coverLoading=false, coverDirty=false, rowNo=0;
 const status=t=>notice.textContent=t;
 const val=id=>($(id)?.value||'').trim();
 function setCover(blob, note){
  if(coverUrl)URL.revokeObjectURL(coverUrl);
  coverBlob=blob;coverUrl=blob?URL.createObjectURL(blob):null;
  previewImage.hidden=!blob;$('preview-image-placeholder').hidden=Boolean(blob);
  if(blob)previewImage.src=coverUrl;else previewImage.removeAttribute('src');
  $('event-cover-status').textContent=note||'Aún no hay portada.';
  $('admin-remove-cover').disabled=!blob;
 }
 function createPrice(data={name:'General',price:80,capacity:0,description:''}){
  const row=element('div','bp-admin__price-row');row.dataset.priceRow='true';rowNo++;
  const top=element('div','bp-admin__price-row-header');
  const title=element('strong','',`Zona ${priceRoot.children.length+1}`);
  const erase=element('button','bp-admin__remove-price','Eliminar zona');erase.type='button';erase.dataset.removePrice='1';
  top.append(title,erase);const fields=element('div','bp-admin__two-col');
  for(const [field,label,kind,max] of [['name','Nombre de zona *','text','75'],['price','Precio en $ *','number','100000000'],['capacity','Cupos disponibles de esta zona *','number','100000']]){
    const group=element('div','bp-field'),labelNode=element('label','bp-label',label),input=element('input','bp-input');
    const id=`zone-${field}-${rowNo}`;labelNode.htmlFor=id;input.id=id;input.dataset.zone=field;input.type=kind;
    input.required=true;if(kind==='number'){input.min=field==='capacity'?'0':'1';input.step='1';input.max=max;}else input.maxLength=Number(max);
    input.value=data[field]??'';group.append(labelNode,input);fields.append(group);
  }
  const detail=element('div','bp-field'),label=element('label','bp-label','Detalle de la zona (opcional)'),input=element('input','bp-input');
  input.id=`zone-description-${rowNo}`;label.htmlFor=input.id;input.dataset.zone='description';input.maxLength=140;
  input.value=data.description||'';detail.append(label,input);
  row.append(top,fields,detail);priceRoot.append(row);syncZoneLabels();
 }
 function syncZoneLabels(){[...priceRoot.children].forEach((row,i)=>{
  row.querySelector('strong').textContent=`Zona ${i+1}`;
  row.querySelector('[data-remove-price]').hidden=priceRoot.children.length===1;
 });}
 function ticketTypes(){return [...priceRoot.querySelectorAll('[data-price-row]')].map(row=>({
  name:row.querySelector('[data-zone=name]').value.trim(),
  price:Number(row.querySelector('[data-zone=price]').value),
  capacity:Number(row.querySelector('[data-zone=capacity]').value),
  description:row.querySelector('[data-zone=description]').value.trim()
 }));}
 function data(){return {
  title:val('event-title'),category:val('event-category'),short:val('event-short'),description:val('event-description'),
  date:val('event-date'),time:val('event-time'),venue:val('event-venue'),city:val('event-city'),
  address:val('event-address'),seating:val('event-seating'),timezone:val('event-timezone'),ticketTypes:ticketTypes()
 };}
 function preview(){const d=data();
  $('preview-title').textContent=d.title||'El nombre de tu evento';$('preview-category').textContent=d.category||'Categoría';
  $('preview-short').textContent=d.short||'Una breve presentación de tu experiencia.';
  $('preview-date').textContent=`${d.date||'Fecha'} · ${d.time||'Hora'}`;
  $('preview-venue').textContent=[d.venue,d.city].filter(Boolean).join(', ')||'Lugar del evento';
  const list=$('preview-price-list');list.replaceChildren();const prices=d.ticketTypes.filter(t=>t.name&&Number.isFinite(t.price)&&t.price>0);
  prices.forEach(t=>{const li=element('li');li.append(element('span','',`${t.name} · ${t.capacity||0} cupos`),element('strong','',`$${t.price.toLocaleString('es-CO')}`));list.append(li);});
  if(!prices.length)list.append(element('li','','Añade una zona con precio válido'));
  $('preview-from').textContent='Desde $'+(prices.length?Math.min(...prices.map(t=>t.price)):0).toLocaleString('es-CO');
 }
 function newForm(){activeId=null;form.reset();$('draft-id').value='';priceRoot.replaceChildren();createPrice();
  removeCover=false;coverDirty=false;setCover(null,'Selecciona una portada para tu evento.');preview();
  status('Nuevo borrador: completa el formulario y guárdalo en el servidor.');}
 async function openEvent(item){
  if(item.status==='pending'){status('Este evento sigue pendiente de revisión y no puede editarse.');return;}
  activeId=item.id;$('draft-id').value=item.id;
  const map={'event-title':'title','event-category':'category','event-short':'short',
   'event-description':'description','event-date':'date','event-time':'time','event-venue':'venue',
   'event-city':'city','event-address':'address','event-seating':'seating','event-timezone':'timezone'};
  for(const [id,key] of Object.entries(map))$(id).value=item[key]||'';
  priceRoot.replaceChildren();item.ticketTypes.forEach(createPrice);
  if(!priceRoot.children.length)createPrice();removeCover=false;setCover(null);
  if(item.hasCover){
   try{const blob=await api.eventCover(item.id);setCover(blob,'Portada recuperada del servidor.');coverDirty=false;}
   catch(error){status(error.message);}
  }
  preview();status(item.status==='approved'?'Editando un evento publicado: se creará una nueva versión para aprobación.':'Editando borrador del servidor.');
  $('crear-evento').scrollIntoView({behavior:'smooth',block:'start'});
 }
 async function refresh(){
  try{events=await api.myEvents();}
  catch(error){status(error.message);return;}
  $('draft-count').textContent=String(events.filter(e=>e.status==='draft'||e.status==='rejected').length);
  const stats=document.querySelectorAll('.bp-admin__stat strong');
  if(stats[1])stats[1].textContent=String(events.filter(e=>e.status==='pending').length);
  if(stats[2])stats[2].textContent=String(events.filter(e=>e.published).length);
  const target=$('admin-drafts');target.replaceChildren();
  if(!events.length){target.append(element('p','bp-admin__empty','Todavía no tienes eventos en el servidor.'));return;}
  for(const item of events){
   const card=element('article','bp-admin__draft-card');
   const state={draft:'BORRADOR',pending:'PENDIENTE DE APROBACIÓN',rejected:'DEVUELTO PARA CORREGIR',approved:'APROBADO'}[item.status]||item.status.toUpperCase();
   card.append(element('small','',`${state} · ${item.hasCover?'CON PORTADA':'SIN PORTADA'}`),
    element('h3','',item.title),element('p','',`${item.category} · ${item.date} · ${item.city}`),
    element('p','',`Desde $${item.minPrice.toLocaleString('es-CO')} · ${item.ticketTypes.length} zona(s)`));
   if(item.review_reason)card.append(element('p','',`Motivo de revisión: ${item.review_reason}`));
   const actions=element('div','bp-admin__draft-actions');
   if(item.status!=='pending'){
    const edit=element('button','bp-admin__outline-button','Editar');edit.type='button';
    edit.addEventListener('click',()=>openEvent(item));actions.append(edit);
   }
   if(item.status==='draft'){
    const submit=element('button','bp-button bp-button--primary','Enviar a revisión');submit.type='button';
    submit.addEventListener('click',async()=>{
     if(!global.confirm(`¿Enviar «${item.title}» para revisión? No podrás editarlo hasta que sea aprobado o devuelto.`))return;
     submit.disabled=true;
     try{const result=await api.submitEvent(item.id);status(result.message);await refresh();}
     catch(error){status(error.message);submit.disabled=false;}
    });actions.append(submit);
   }
   if(item.published){const view=element('a','bp-admin__outline-button','Ver ficha pública');
    view.href=`../event-detail.html?id=live-${item.id}`;actions.append(view);}
   card.append(actions);target.append(card);
  }
 }
 async function chooseFile(file){if(!file)return;
  coverLoading=true;status('Procesando imagen...');
  try{const blob=await coverTools.prepare(file);setCover(blob,`${file.name} · lista para guardar en servidor`);
   coverDirty=true;removeCover=false;status('Foto lista: pulsa Guardar borrador para subirla.');}
  catch(error){status(error.message||'No se pudo procesar la portada.');}
  finally{coverLoading=false;coverInput.value='';}
 }
 coverInput.addEventListener('change',()=>void chooseFile(coverInput.files?.[0]));
 $('admin-remove-cover').addEventListener('click',()=>{removeCover=true;setCover(null,'Portada retirada. Guarda para confirmar el cambio.');});
 const drop=$('admin-cover-dropzone');
 drop.addEventListener('dragover',e=>{e.preventDefault();drop.classList.add('is-dragging');});
 drop.addEventListener('dragleave',()=>drop.classList.remove('is-dragging'));
 drop.addEventListener('drop',e=>{e.preventDefault();drop.classList.remove('is-dragging');void chooseFile(e.dataTransfer?.files?.[0]);});
 priceRoot.addEventListener('click',e=>{const button=e.target.closest('[data-remove-price]');
  if(button&&priceRoot.children.length>1){button.closest('[data-price-row]').remove();syncZoneLabels();preview();}});
 $('admin-add-price').addEventListener('click',()=>{if(priceRoot.children.length>=12)return status('Máximo 12 zonas por evento.');
  createPrice({name:'',price:80,capacity:0,description:''});preview();});
 form.addEventListener('input',preview);form.addEventListener('change',preview);
 $('admin-clear-form').addEventListener('click',newForm);
 form.addEventListener('submit',async e=>{
  e.preventDefault();if(coverLoading)return status('Termina de procesar la portada.');
  if(!form.reportValidity())return status('Revisa los campos obligatorios.');
  const body=data();
  if(body.ticketTypes.some(t=>!t.name||!Number.isInteger(t.price)||t.price<1||!Number.isInteger(t.capacity)||t.capacity<0))return status('Las zonas necesitan nombre, precio positivo y capacidad válida (0 significa sin venta).');
  const submit=form.querySelector('button[type=submit]');submit.disabled=true;status('Guardando en la API...');
  try{
   const updated=activeId?await api.updateEvent(activeId,body):await api.createEvent(body);
   activeId=updated.id;$('draft-id').value=String(activeId);
   if(removeCover){await api.removeEventCover(activeId);removeCover=false;coverDirty=false;}
   if(coverBlob && coverDirty){await api.uploadEventCover(activeId,coverBlob);coverDirty=false;}
   status('Borrador guardado en el servidor. Puedes enviarlo a revisión desde «Mis eventos».');
   await refresh();
  }catch(error){status(error.message||'Error guardando el evento.');}
  finally{submit.disabled=false;}
 });
 newForm();await refresh();
 global.addEventListener('pagehide',()=>{if(coverUrl)URL.revokeObjectURL(coverUrl);});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else void init();
})(window);
