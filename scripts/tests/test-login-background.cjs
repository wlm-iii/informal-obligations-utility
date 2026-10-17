const fs=require('fs'),vm=require('vm'),assert=require('assert');
const path=require('path');
const html=fs.readFileSync(path.resolve(__dirname,'../../frontend/public/IOU-Terminal-Login.html'),'utf8');
for(const script of html.matchAll(/<script>([\s\S]*?)<\/script>/g))new vm.Script(script[1]);
const source=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]).find(s=>s.includes("const count=60,step="));
class El{constructor(){this.style={};this.attrs={};this.children=[];this.dataset={pattern:'market'};this.classList={contains:()=>false}}setAttribute(k,v){this.attrs[k]=v}replaceChildren(){this.children=[]}append(...children){this.children.push(...children)}getBoundingClientRect(){return{top:100,height:260}}}
const ids=Object.fromEntries(['patternBackground','headlineMarket','tickerScroll','tickerArea','tickerLine','tickerTags'].map(id=>[id,new El()]));ids.headlineMarket.parentElement=new El();
const headline=new El(),intro=new El();intro.querySelector=()=>headline;
let callback=null,mutate;const reduced={matches:false,addEventListener(){}};
const context={document:{getElementById:id=>ids[id],querySelector:()=>intro,createElementNS:()=>new El(),addEventListener(){},hidden:false},window:{addEventListener(){}},matchMedia:()=>reduced,MutationObserver:class{constructor(cb){mutate=cb}observe(){}},ResizeObserver:class{observe(){}},requestAnimationFrame:cb=>{callback=cb;return 1},cancelAnimationFrame:()=>{callback=null}};
vm.runInNewContext(source,context);
const start=ids.tickerLine.attrs.d;callback(0);for(let t=100;t<=900;t+=100)callback(t);assert.equal(ids.tickerLine.attrs.d,start,'Values must stay fixed before one second');assert(Number(ids.tickerScroll.attrs.transform.match(/-?[\d.]+/)[0])<0,'Chart must move left');callback(1000);assert.notEqual(ids.tickerLine.attrs.d,start,'New sample at one second');assert(!/NaN|undefined/.test(ids.tickerArea.attrs.d));
ids.patternBackground.classList.contains=()=>true;mutate();assert.equal(callback,null,'Pause must cancel frames');ids.patternBackground.classList.contains=()=>false;reduced.matches=true;mutate();assert.equal(callback,null,'Reduced motion must stay static');
assert.equal(ids.headlineMarket.parentElement.style.height,'395px');console.log('Passed: 1-second samples, leftward scroll, finite area path, headline sizing, pause, reduced motion.');
