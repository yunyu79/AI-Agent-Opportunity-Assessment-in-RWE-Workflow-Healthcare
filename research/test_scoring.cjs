const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const html=fs.readFileSync(process.argv[2]||'scenario_prioritization.html','utf8');
const scripts=[...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(x=>x[1]);
const context={};vm.createContext(context);vm.runInContext(scripts[0],context);
const S=context.ScenarioScoring;const defaults=Object.fromEntries(S.metrics.map(m=>[m.key,m.weight]));
const rows=S.rank(S.scenarios,defaults).rows;
assert.equal(rows[0].id,'W04');
assert.ok(Math.abs(rows[0].score-56.34375)<1e-8);
assert.ok(Math.abs(Object.values(S.normalizedWeights(defaults)).reduce((a,b)=>a+b,0)-1)<1e-12);
const zero=Object.fromEntries(S.metrics.map(m=>[m.key,0]));assert.equal(S.rank(S.scenarios,zero).rows.length,0);
assert.equal(S.rank(S.scenarios,{...zero,hours:100}).rows[0].id,'W01');
assert.equal(S.rank(S.scenarios,{...zero,frequency:100}).rows[0].id,'W05');
assert.equal(S.rank(S.scenarios,{...zero,collaboration:100}).rows[0].id,'W05');
assert.equal(S.rank(S.scenarios,defaults).rows.find(r=>r.id==='W09').values.collaboration,0);
for(const [rate,level] of [[0,1],[.999,1],[1,2],[2.99,2],[3,3],[4.99,3],[5,4],[9.99,4],[10,5],[100,5]])assert.equal(S.errorLevel(rate),level);
assert.equal(S.errorLevel(-1),null);assert.equal(S.errorLevel(null),null);
let altered=JSON.parse(JSON.stringify(S.scenarios));altered[0].afterHours=400;altered[0].afterError=6;
let r=S.rank(altered,defaults).rows.find(r=>r.id==='W01');assert.ok(r.values.hours<0);assert.ok(r.values.errors<0);assert.equal(r.hold,true);
altered=JSON.parse(JSON.stringify(S.scenarios));altered[0].frequency=null;assert.equal(S.rank(altered,defaults).rows.find(r=>r.id==='W01').score,null);
altered=JSON.parse(JSON.stringify(S.scenarios));altered[0].beforeRepeat=2.5;assert.equal(S.validate(altered[0]).length,1);
altered=[{...S.scenarios[0],id:'A'},{...S.scenarios[0],id:'B'}];assert.equal(S.rank(altered,defaults).rows[0].rank,S.rank(altered,defaults).rows[1].rank);
assert.equal(S.rank(S.scenarios,{...defaults,hours:-1}).rows.length,0);
for(const script of scripts)new Function(script);
console.log('PASS: default ranking, weight normalization, zero weights, slider sensitivity, error-scale boundaries, negative gains, quality holds, missing data, ordinal validation, ties, and JavaScript syntax.');

// Exercise the browser controller against a minimal DOM, including slider/input events.
const nodes={};
class Element {
 constructor(tag){this.tag=tag;this.children=[];this.style={};this.attributes={};this.value='';this.textContent='';}
 set id(v){this._id=v;nodes[v]=this;} get id(){return this._id;}
 append(...items){this.children.push(...items);} appendChild(item){this.append(item);return item;}
 replaceChildren(...items){this.children=[...items];}
 setAttribute(k,v){this.attributes[k]=v;}
 createTHead(){const e=new Element('thead');this.append(e);return e;}
 createTBody(){const e=new Element('tbody');this.append(e);return e;}
 insertRow(){const e=new Element('tr');this.append(e);return e;}
 insertCell(){const e=new Element('td');this.append(e);return e;}
}
for(const id of ['controls','legend','inputs','chart','contributions','error','leader','reset','download']){const e=new Element('div');e.id=id;}
context.document={getElementById:id=>nodes[id],createElement:tag=>new Element(tag),createTextNode:text=>({textContent:text})};
context.setTimeout=setTimeout;context.Blob=Blob;context.URL=URL;
vm.runInContext(scripts[1],context);
assert.ok(nodes.leader.textContent.includes('W04'));
for(const m of S.metrics){nodes['w-'+m.key].value=0;nodes['w-'+m.key].oninput();}
assert.ok(nodes.error.textContent.includes('at least one'));
nodes['w-frequency'].value=100;nodes['w-frequency'].oninput();
assert.ok(nodes.leader.textContent.includes('W05'));
nodes.reset.onclick();assert.ok(nodes.leader.textContent.includes('W04'));
console.log('PASS: controller initialization, slider events, all-zero state and reset update the displayed leader.');
