from pathlib import Path
import shutil
import subprocess
import pytest


def test_batch_states_and_correction_isolation():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required")
    root = Path(__file__).resolve().parents[1]
    setup = r"""
const assert=require('node:assert/strict');
class Element {
 constructor(){this.value='';this.checked=false;this.children=[];this.textContent='';this.style={};this.classList={toggle(){}};}
 append(...nodes){this.children.push(...nodes);} replaceChildren(...nodes){this.children=nodes;}
 scrollIntoView(){} addEventListener(){} setAttribute(){} add(node){this.children.push(node);} querySelector(){return new Element();}
}
const elements=new Map();global.document={getElementById(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id);},createElement(){return new Element();},createDocumentFragment(){return new Element();},querySelector(){return new Element();},querySelectorAll(){return [];}};
global.window={addEventListener(){}};global.Option=class extends Element{};
const parsed=(hash,num)=>({file_hash:hash,invoice_number:num,items:[{row_number:1,brand:'Original',ean:'0012345678901',warnings:[],raw_lines:[]}],pages:1,item_count:1,warnings:[],rows_with_warnings:0,duplicate_eans:{}});
let replies=[];global.fetch=async()=>{const item=replies.shift();if(item instanceof Error)throw item;return {ok:item.ok!==false,status:item.status||200,json:async()=>item.data};};
"""
    script = (root / "app/static/js/preview.js").read_text(encoding="utf-8")
    checks = r"""
(async()=>{
 const first={file:new File(['pdf'],'first.pdf'),state:'waiting'};
 const failed={file:new File(['bad'],'bad.pdf'),state:'waiting'};
 const second={file:new File(['pdf2'],'second.pdf'),state:'waiting'};
 queue=[first,failed,second];
 replies=[{data:parsed('one','1')},{data:{imported:false}},{ok:false,data:{detail:'PDF kaputt'}},{data:parsed('two','2')},{data:{imported:false}}];
 for(const entry of queue)await readEntry(entry);
 assert.equal(first.state,'ready');assert.equal(failed.state,'error');assert.equal(second.state,'ready');
 selectEntry(0);data.items[0].brand='Korrigiert';validated=false;saveCurrent();
 selectEntry(2);assert.equal(data.items[0].brand,'Original');assert.equal(validated,true);
 selectEntry(0);assert.equal(data.items[0].brand,'Korrigiert');assert.equal(validated,false);assert.equal(getEdits()['1'].brand,'Korrigiert');
 const duplicate={file:new File(['pdf'],'copy.pdf')};queue.push(duplicate);replies=[{data:parsed('one','1')}];await readEntry(duplicate);assert.equal(duplicate.state,'duplicate');
 const existing={file:new File(['pdf3'],'existing.pdf')};queue.push(existing);replies=[{data:parsed('three','3')},{data:{imported:true,invoice_id:88}}];await readEntry(existing);assert.equal(existing.state,'imported');assert.equal(existing.invoiceId,88);
 selectEntry(4);assert.equal(previewFile,null);assert.equal(document.getElementById('confirm').disabled,true);
 replies=[{data:parsed('retry','4')},{data:{imported:false}}];await readEntry(failed);assert.equal(failed.state,'ready');
 assert.equal(replies.length,0);
 let destination=null;global.location={assign(url){destination=url;}};
 queue=[first,second,failed];active=0;first.state='imported';
 advanceAfterImport();assert.equal(active,1);assert.equal($('confirm').checked,false);
 second.state='imported';advanceAfterImport();assert.equal(active,2);
 failed.state='imported';first.state='error';advanceAfterImport();assert.equal(destination,null);
 first.state='duplicate';advanceAfterImport();assert.equal(destination,'/');

})().catch(e=>{console.error(e);process.exitCode=1;});
"""
    result = subprocess.run(
        [node, "-"],
        input=(setup + script + checks).encode(),
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr.decode()
