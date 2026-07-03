let current={nodes:[],edges:[]}, depth=1, focusedEntity=null;
const details=document.querySelector('#details');
const cy=cytoscape({container:document.querySelector('#cy'),elements:[],style:[
 {selector:'node',style:{label:'data(label)','background-color':'#4ca3dd','font-size':10,color:'#dbeafa','text-valign':'bottom'}},
 {selector:'node[type="case"]',style:{'background-color':'#dc9c3f'}},{selector:'node[type="validator"]',style:{'background-color':'#8a6dde'}},
 {selector:'edge',style:{label:'data(label)',width:2,'line-color':'#647b8e','target-arrow-color':'#647b8e','target-arrow-shape':'triangle','curve-style':'bezier','font-size':8,color:'#aabac7'}},
 {selector:'.dim',style:{opacity:.12}},{selector:'.selected-route',style:{'line-color':'#ffcb57','target-arrow-color':'#ffcb57',width:5}}
],layout:{name:'cose',animate:false}});
async function get(url){const response=await fetch(url);if(!response.ok)throw new Error(await response.text());return response.json()}
function show(graph){current=graph;cy.elements().remove();cy.add([...graph.nodes,...graph.edges]);cy.layout({name:'cose',animate:false}).run();populateCases()}
function populateCases(){const select=document.querySelector('#case');const values=[...new Set(current.nodes.map(x=>x.data).filter(x=>x.type==='case').map(x=>x.label))];select.innerHTML='<option value="">Choose from graph</option>'+values.map(x=>`<option>${x}</option>`).join('')}
async function overview(){focusedEntity=null;depth=1;show(await get('/api/graph/overview'))}
document.querySelector('#entity-form').onsubmit=async e=>{e.preventDefault();const q=document.querySelector('#entity').value;const found=await get('/api/entity/search?q='+encodeURIComponent(q));const picker=document.querySelector('#entity-candidates');picker.innerHTML=found.results.map(x=>`<option value="${x.id}">${x.label}</option>`).join('');picker.hidden=found.results.length<2;if(found.results.length){focusedEntity=found.results[0].id;show(await get(`/api/entity/${encodeURIComponent(focusedEntity)}/neighborhood?depth=${depth}`))}};
document.querySelector('#entity-candidates').onchange=async e=>{focusedEntity=e.target.value;show(await get(`/api/entity/${encodeURIComponent(focusedEntity)}/neighborhood?depth=${depth}`))};
document.querySelector('#triple-form').onsubmit=async e=>{e.preventDefault();const p=new URLSearchParams({subject:subject.value,predicate:predicate.value,object:object.value});show(await get('/api/triple/search?'+p))};
document.querySelector('#path-form').onsubmit=async e=>{e.preventDefault();const p=new URLSearchParams({source:document.querySelector('#path-source').value,target:document.querySelector('#path-target').value,max_depth:document.querySelector('#max-depth').value});show(await get('/api/path?'+p))};
document.querySelector('#case').onchange=async e=>{if(e.target.value)show(await get('/api/graph/case/'+encodeURIComponent(e.target.value)))};
document.querySelector('#reset').onclick=overview;document.querySelector('#expand').onclick=async()=>{if(focusedEntity){depth=Math.min(depth+1,3);show(await get(`/api/entity/${encodeURIComponent(focusedEntity)}/neighborhood?depth=${depth}`))}};
document.querySelector('#export').onclick=()=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(current,null,2)],{type:'application/json'}));a.download='system-b-subgraph.json';a.click();URL.revokeObjectURL(a.href)};
cy.on('tap','node',async event=>{const data=event.target.data();details.textContent=JSON.stringify(data,null,2);if(data.type==='entity'){focusedEntity=data.id;show(await get(`/api/entity/${encodeURIComponent(data.id)}/neighborhood?depth=${depth}`))}});
cy.on('tap','edge',async event=>{const edge=event.target;cy.elements().addClass('dim');edge.removeClass('dim').addClass('selected-route');edge.connectedNodes().removeClass('dim');const data=edge.data(), snippets=[];for(const id of data.evidence_ids||[]){try{snippets.push(await get('/api/evidence/'+encodeURIComponent(id)))}catch{}}details.textContent=JSON.stringify({...data,evidence:snippets},null,2)});
overview().catch(error=>details.textContent=String(error));
