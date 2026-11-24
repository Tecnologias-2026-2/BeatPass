// FLUJO: catalog.html -> api.publicEvents(q,category,limit,offset) -> events.py -> tarjeta compartida.
/** Consulta los eventos aprobados y pagina resultados en la API. */
(function(global){
'use strict';
async function init(){
  const app=global.BeatPass,grid=document.getElementById('events-grid');if(!grid)return;
  const search=document.getElementById('search-input'),filters=[...document.querySelectorAll('.category-btn')];
  const label=document.createElement('p');label.className='bp-catalog-note';label.setAttribute('role','status');
  grid.parentElement.insertBefore(label,grid);
  const more=document.createElement('button');more.type='button';more.className='bp-catalog-more';
  more.textContent='Cargar más eventos';more.hidden=true;grid.after(more);
  let category='all',mode='live',examples=[],offset=0,generation=0,debounce;
  const PAGE_SIZE=24;
  const norm=x=>String(x||'').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');
  const searchTerm=()=>search?.value.trim() || '';
  function showExamples(message){
    mode='examples';examples=app.demoEvents||[];label.textContent=message;
    more.hidden=true;renderExamples();
  }
  function renderExamples(){
    const q=norm(searchTerm());
    const filtered=examples.filter(x=>(category==='all'||norm(x.category)===category)&&
      (!q||norm([x.title,x.venue,x.city,x.short].join(' ')).includes(q)));
    grid.replaceChildren(...filtered.map(x=>app.eventCard(x,{demo:true,catalog:true})));
    if(!filtered.length){const p=document.createElement('p');p.textContent='No hay eventos que coincidan.';grid.append(p);}
  }
  async function loadNext(reset=false){
    if(reset){generation++;offset=0;grid.replaceChildren();}
    if(mode==='examples'){renderExamples();return;}
    const current=generation;more.disabled=true;label.textContent='Consultando eventos aprobados...';
    try{
      const rows=await app.api.publicEvents({q:searchTerm(),category:category==='all'?'':(category==='musica'?'Música':category[0].toUpperCase()+category.slice(1)),limit:PAGE_SIZE,offset});
      if(current!==generation)return;
      if(!offset && !rows.length && !searchTerm() && category==='all'){
        if ((app.demoEvents || []).length) showExamples('Todavía no hay eventos aprobados. Estos son ejemplos, no entradas a la venta.');
        else {mode='live';label.textContent='Todavía no hay eventos publicados.';more.hidden=true;}
        return;
      }
      grid.append(...rows.map(x=>app.eventCard(x,{catalog:true})));
      offset+=rows.length;more.hidden=rows.length<PAGE_SIZE;
      label.textContent=grid.children.length?`${offset} evento(s) publicados encontrados.`:'No hay eventos que coincidan con esta búsqueda.';
    }catch(_error){if(current!==generation)return;
      if(!offset && !searchTerm() && category==='all' && (app.demoEvents || []).length)showExamples('No se puede consultar el catálogo. Solo se muestran ejemplos.');
      else{label.textContent='No fue posible consultar el catálogo. Vuelve a intentarlo.';more.hidden=true;}
    }finally{if(current===generation)more.disabled=false;}
  }
  search?.addEventListener('input',()=>{clearTimeout(debounce);debounce=setTimeout(()=>{
    if(mode==='examples')renderExamples();else void loadNext(true);
  },250);});
  filters.forEach(button=>button.addEventListener('click',()=>{
    category=button.dataset.category;filters.forEach(b=>{const on=b===button;b.classList.toggle('active',on);b.setAttribute('aria-pressed',String(on));});
    if(mode==='examples')renderExamples();else void loadNext(true);
  }));
  more.addEventListener('click',()=>void loadNext());
  void loadNext(true);
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>void init());else void init();
})(window);
