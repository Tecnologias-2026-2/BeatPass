/** FLUJO: profile.html -> profile.js -> api.js; DOM simulado, sin red ni datos reales. */
const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const ids=['profile-status','profile-private','profile-guest','profile-owner','profile-avatar',
 'profile-email-display','profile-email','profile-name','profile-roles','profile-verification',
 'profile-organization-panel','profile-organization-info','profile-organizer-link',
 'profile-name-form','profile-password-form','profile-name-message','profile-password-message',
 'profile-name-submit','profile-password-submit','profile-current-password',
 'profile-new-password','profile-confirm-password'];
const nodes=Object.fromEntries(ids.map(id=>[id,{hidden:false,textContent:'',value:'',dataset:{},disabled:false,
 listeners:{},addEventListener(name,cb){this.listeners[name]=cb;},reportValidity(){return true;},reset(){this.resetCalled=true;}}]));
let user={id:15, fullname:'Ana Rivera',email:'ana@example.test',email_verified:true,
 roles:['cliente'], organization:null};
const actions=[];
const api={
 async profile(){actions.push('GET /api/profile');return {...user};},
 async updateProfile(fullname){actions.push('PATCH /api/profile');user={...user,fullname};return {user:{...user},message:'Nombre actualizado.'};},
 async changePassword(oldPwd,newPwd){actions.push('POST /api/profile/change-password');assert.equal(oldPwd,'anterior-123456');assert.equal(newPwd,'nuevo-12345678');return {message:'Sesión invalidada.'};}
};
let sessionPresent=true, lastSaved=null,clearCount=0;
const session={token:()=>sessionPresent?'token':null,currentUser:()=>sessionPresent?user:null,
 save(_token,newUser){lastSaved=newUser;},clear(){sessionPresent=false;clearCount++;}};
const window={BeatPass:{api,session}};
const document={getElementById:id=>nodes[id]};
const src=fs.readFileSync(path.join(__dirname,'../js/pages/profile.js'),'utf8');
const tick=()=>new Promise(r=>setImmediate(r));
(async()=>{
 vm.runInNewContext(src,{window,document}); await tick();
 assert.equal(nodes['profile-owner'].textContent,'Ana Rivera');
 assert.equal(nodes['profile-private'].hidden,false);
 assert.equal(nodes['profile-email'].value,'ana@example.test');
 assert.equal(nodes['profile-organization-panel'].hidden,true);
 nodes['profile-name'].value='Ana Nueva';
 await nodes['profile-name-form'].listeners.submit({preventDefault(){},target:nodes['profile-name-form']});
 assert.equal(nodes['profile-owner'].textContent,'Ana Nueva');
 assert.equal(lastSaved.fullname,'Ana Nueva');
 nodes['profile-current-password'].value='anterior-123456';
 nodes['profile-new-password'].value='nuevo-12345678';
 nodes['profile-confirm-password'].value='otro';
 await nodes['profile-password-form'].listeners.submit({preventDefault(){},target:nodes['profile-password-form']});
 assert.equal(clearCount,0);assert.equal(nodes['profile-password-message'].dataset.state,'error');
 nodes['profile-confirm-password'].value='nuevo-12345678';
 await nodes['profile-password-form'].listeners.submit({preventDefault(){},target:nodes['profile-password-form']});
 assert.equal(clearCount,1);
 assert.equal(nodes['profile-private'].hidden,true);
 assert.equal(nodes['profile-guest'].hidden,false);
 assert.deepEqual(actions,['GET /api/profile','PATCH /api/profile','GET /api/profile','POST /api/profile/change-password']);
 console.log('OK: Mi perfil carga, actualiza saludo, comprueba contraseñas y cierra sesión.');
})().catch(error=>{console.error(error);process.exitCode=1;});
