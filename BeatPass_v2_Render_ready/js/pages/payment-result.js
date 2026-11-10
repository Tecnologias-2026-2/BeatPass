// FLUJO: payment-result.html -> api.myOrder() -> orders.py. NO confiar en los parámetros del retorno.
(function(global){
'use strict';
async function init(){
 const app=global.BeatPass;
 const target=document.getElementById('payment-result-message');
 const orderId=Number(new URLSearchParams(global.location.search).get('order_id'));
 const button=document.getElementById('payment-refresh');
 if(!Number.isSafeInteger(orderId)||orderId<=0){target.textContent='Pedido inválido.';button.disabled=true;return;}
 async function refresh(){
   button.disabled=true;target.textContent='Consultando al servidor...';
   try{
     const order=await app.api.myOrder(orderId);
     const labels={reserved:'Pago todavía pendiente de confirmación. Revisa de nuevo antes de que venza la reserva.',
       sandbox_paid:'Pago de PRUEBA confirmado por el servidor. Ya puedes consultar tus boletos DEMO.',
       demo_confirmed:'Compra DEMO confirmada, sin dinero cobrado.',expired:'Reserva vencida. No se emitieron boletos.',
       cancelled:'Reserva cancelada.',};
     target.textContent=labels[order.status]||`Estado del pedido: ${order.status}`;
     if(order.payment?.status==='late_approved')target.textContent+=' El pago de prueba llegó tarde: requiere conciliación manual.';
   }catch(error){target.textContent=error.message;}
   finally{button.disabled=false;}
 }
 button.addEventListener('click',()=>void refresh());
 void refresh();
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>void init());else void init();
})(window);
