const assert=require('node:assert/strict'),path=require('node:path'),{pathToFileURL}=require('node:url'),fs=require('node:fs'),vm=require('node:vm');
(async()=>{
 const root=path.resolve(__dirname,'../..');
 const {loginRequest}=await import(pathToFileURL(path.join(root,'frontend/src/services/login.js')));
 let oauth,password;const auth={signInWithOAuth:async input=>{oauth=input;return{error:null}},signInWithPassword:async input=>{password=input;return{error:null}}};
 await loginRequest(auth,{action:'google'},'http://localhost:5173');assert.deepEqual(oauth,{provider:'google',options:{redirectTo:'http://localhost:5173/auth/callback'}});
 await loginRequest(auth,{action:'password',email:' person@example.com ',password:'test-password'},'http://localhost:5173');assert.deepEqual(password,{email:'person@example.com',password:'test-password'});
 await assert.rejects(loginRequest(null,{action:'google'},''),/not configured/);
 await assert.rejects(loginRequest(auth,{action:'password',email:'a',password:''},''),/Enter your email/);
 await assert.rejects(loginRequest({signInWithPassword:async()=>({error:Error('secret-provider-detail')})},{action:'password',email:'a',password:'b'},''),e=>!e.message.includes('secret-provider-detail')&&e.message.includes('Unable to sign in'));
 const html=fs.readFileSync(path.join(root,'frontend/public/IOU-Terminal-Login.html'),'utf8');const script=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]).find(s=>s.includes("get('connected')"));
 const elements=Object.fromEntries(['loginStatus','google','signin','password','email'].map(id=>[id,{style:{},value:''}]));elements.email.value='person@example.com';elements.password.value='test-password';let sent,reply;const handlers={};const parent={postMessage:(data,origin)=>{sent={data,origin}}};const location={search:'?connected=1',origin:'http://localhost:5173'};const context={location,parent,URLSearchParams,document:{getElementById:id=>elements[id],querySelector:()=>({}),addEventListener:(name,fn)=>handlers[name]=fn},window:{addEventListener:(_,fn)=>reply=fn}};
 vm.runInNewContext(script,context);handlers.submit({target:{id:'loginForm'},preventDefault(){},stopImmediatePropagation(){}});
 assert.equal(sent.data.action,'password');assert.equal(sent.data.password,'test-password');assert.equal(sent.origin,location.origin);assert.equal(elements.password.value,'');assert.equal(elements.signin.disabled,true);
 reply({source:parent,origin:'https://other.example',data:{type:'iou:login-result',error:'fake'}});assert.equal(elements.signin.disabled,true);
 reply({source:parent,origin:location.origin,data:{type:'iou:login-result',error:'Try Google'}});assert.equal(elements.signin.disabled,false);assert.equal(elements.loginStatus.textContent,'Try Google');
 console.log('Passed: OAuth callback, password handoff, validation, safe errors, same-origin replies, credential clearing, loading recovery.');
})().catch(error=>{console.error(error);process.exitCode=1});
