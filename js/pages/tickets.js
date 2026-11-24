// FLUJO: tickets.html -> api.js -> backend/orders.py -> tablas issued_tickets.
/** Mis boletos demo: solo muestra entradas que pertenecen a la sesión verificada. */
(function (global) {
  'use strict';
  const app=global.BeatPass;
  const $=id=>document.getElementById(id);
  const text=(tag,cls,value)=>{const e=document.createElement(tag);if(cls)e.className=cls;e.textContent=value;return e;};
  const money=n=>Number(n).toLocaleString('es-CO');
  const status={reserved:'Reserva activa',expired:'Reserva vencida',cancelled:'Cancelada',demo_confirmed:'Confirmación DEMO',sandbox_paid:'Pago TEST confirmado'};
  function init() {
    const grid=$('tickets-grid'),empty=$('empty-tickets-state');if(!grid)return;
    const section=document.createElement('section');section.className='bp-ticket-orders';
    section.append(text('h2','','Mis pedidos y pagos de prueba'));
    const history=document.createElement('div');history.className='bp-ticket-orders__list';section.append(history);
    grid.before(section);
    const message=text('p','bp-tickets-message','Cargando entradas...');grid.before(message);
    const references=[];
    const cleanup=()=>references.splice(0).forEach(url=>URL.revokeObjectURL(url));
    global.addEventListener('pagehide',cleanup,{once:true});
    async function load() {
      cleanup(); grid.replaceChildren();history.replaceChildren();
      if (!app.session?.token()) {
        message.textContent='Inicia sesión para ver tus boletos y pedidos.';
        empty.style.display='flex';
        const cta=empty.querySelector('.empty-tickets-cta');if(cta){cta.href='login.html';cta.querySelector('span').textContent='Iniciar sesión';}
        return;
      }
      try {
        const [tickets,orders]=await Promise.all([app.api.myTickets(),app.api.myOrders()]);
        message.textContent='Las entradas de esta etapa son DEMO. No sirven para entrar ni acreditan un pago.';
        empty.style.display=tickets.length?'none':'flex';
        section.hidden=!orders.length;
        orders.forEach(order=>{
          const article=text('article','bp-order-card',`Pedido #${order.id} · ${status[order.status]||order.status}`);
          article.append(text('span','',`$${money(order.subtotal)} COP · ${order.items.reduce((n,line)=>n+line.quantity,0)} entradas`));
          if(order.status==='reserved')article.append(text('small','',`Caduca: ${new Date(order.expires_at).toLocaleString('es-CO')}`));
          history.append(article);
        });
        tickets.forEach(ticket=>{
          const article=document.createElement('article');article.className='ticket-card bp-ticket-demo';article.setAttribute('role','listitem');
          const cover=document.createElement('div');cover.className='ticket-image';
          const image=document.createElement('img');image.alt=`Portada de ${ticket.event_title}`;
          image.src=app.api.assetUrl(ticket.image_url)||'../assets/visuals/concierto.svg';
          image.onerror=()=>{image.onerror=null;image.src='../assets/visuals/concierto.svg';};cover.append(image);
          const content=document.createElement('div');content.className='ticket-content';
          content.append(text('span','bp-ticket-demo__label','BOLETO DE PRUEBA · NO VÁLIDO PARA ACCESO'));
          content.append(text('h3','ticket-title',ticket.event_title));
          content.append(text('p','ticket-detail',`${ticket.zone_name} · ${ticket.date} · ${ticket.time}`));
          content.append(text('p','ticket-detail',`${ticket.venue}, ${ticket.city}`));
          content.append(text('small','',`ID: ${ticket.code.slice(0,12)} · Pedido #${ticket.order_id}`));
          const qrBtn=text('button','bp-ticket-demo__button','Ver QR de demostración');qrBtn.type='button';
          const qr=document.createElement('div');qr.className='bp-ticket-demo__qr';qr.hidden=true;
          qrBtn.addEventListener('click',async()=>{
            if(!qr.hidden){qr.hidden=true;qrBtn.textContent='Ver QR de demostración';return;}
            qrBtn.disabled=true;qrBtn.textContent='Cargando QR...';
            try {
              const blob=await app.api.ticketQr(ticket.id);
              const url=URL.createObjectURL(blob);references.push(url);
              const img=document.createElement('img');img.src=url;img.alt='QR de prueba, no válido para acceso';
              qr.replaceChildren(img,text('small','','Solo para pruebas del sistema; no permite ingresar al evento.'));
              qr.hidden=false;qrBtn.textContent='Ocultar QR';
            } catch(error){qr.replaceChildren(text('small','',error.message));qr.hidden=false;qrBtn.textContent='Reintentar QR';}
            finally{qrBtn.disabled=false;}
          });
          content.append(qrBtn,qr);article.append(cover,content);grid.append(article);
        });
      } catch(error) {
        message.textContent=error.message;
        empty.style.display='flex';
        if(error.status===401)app.session?.clear();
      }
    }
    void load();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})(window);
