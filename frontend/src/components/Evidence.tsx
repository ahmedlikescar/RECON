import { useMemo, useState } from 'react';
import { ReactFlow, Background, Controls, MarkerType } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Code2, GitBranch, Info } from 'lucide-react';
import { address } from '../api';
import type { FunctionDetail } from '../api';

export function Instructions({detail}:{detail:FunctionDetail}) {
  const [shown,setShown]=useState(200);
  return <div className="instruction-scroll"><table className="instructions"><thead><tr><th>Address</th><th>Instruction</th><th>Operands</th></tr></thead><tbody>{detail.instructions.slice(0,shown).map(i=><tr key={i.address} className={['conditional','jump'].includes(i.flow)?'branch-row':''}><td>{address(i.address)}</td><td className={`op op-${i.flow}`}>{i.mnemonic}</td><td>{i.operands}</td></tr>)}</tbody></table>{detail.instructions.length>shown&&<button className="button ghost" onClick={()=>setShown(n=>n+200)}>Show more instructions ({detail.instructions.length-shown} remaining)</button>}</div>;
}
export function Graph({detail}:{detail:FunctionDetail}) {
  const nodes=useMemo(()=>detail.cfg.blocks.map((block,index)=>({id:block.id,position:{x:(index%3)*235,y:Math.floor(index/3)*155},
    data:{label:<div className="cfg-node"><strong>{address(block.start_address)}</strong>{detail.instructions.filter(i=>block.instruction_addresses.includes(i.address)).slice(0,4).map(i=><span key={i.address}>{i.mnemonic} {i.operands}</span>)}{block.instruction_addresses.length>4&&<span>… {block.instruction_addresses.length-4} more</span>}</div>},style:{background:'#1c2024',color:'#c9ced4',border:'1px solid #414950',borderRadius:6,width:210,fontFamily:'monospace',fontSize:11}})),[detail]);
  const edges=useMemo(()=>detail.cfg.edges.map((edge,index)=>({id:String(index),source:edge.source,target:edge.target,label:edge.kind==='branch'?'branch':'',style:{stroke:edge.kind==='branch'?'#e9a06d':'#64727a'},markerEnd:{type:MarkerType.ArrowClosed,color:'#78848b'}})),[detail]);
  return <div className="cfg-canvas" aria-label={`Control flow graph of ${detail.name}`}><ReactFlow nodes={nodes} edges={edges} fitView colorMode="dark" nodesDraggable={false} proOptions={{hideAttribution:true}}><Background color="#343b41" gap={20}/><Controls showInteractive={false}/></ReactFlow></div>;
}
export default function Evidence({detail,compact=false}:{detail:FunctionDetail|null; compact?:boolean}) {
  const [view,setView]=useState<'instructions'|'cfg'>('instructions');
  if(!detail)return <div className="empty-pane"><Code2 size={30}/><p>Select a function to inspect its evidence.</p></div>;
  return <section className={`evidence ${compact?'compact':''}`}><div className="evidence-head"><div><span className="eyebrow">FUNCTION EVIDENCE</span><h3>{detail.name}</h3><div className="mono muted">{address(detail.address)} <span>→</span> {address(detail.end_address)}</div></div><span className="tag">{detail.instructions.length} instructions</span></div><div className="evidence-tabs"><button className={view==='instructions'?'active':''} onClick={()=>setView('instructions')}><Code2 size={14}/>Instructions</button><button className={view==='cfg'?'active':''} onClick={()=>setView('cfg')}><GitBranch size={14}/>Control flow <span>{detail.cfg.blocks.length}</span></button></div>{view==='instructions'?<Instructions key={detail.id} detail={detail}/>:<Graph detail={detail}/>}<div className="evidence-notes"><Info size={14}/><div><span>Discovery: {detail.discovery_method.replaceAll('_',' ')} · confidence {detail.confidence.toFixed(2)}</span>{detail.limitations.map(note=><p key={note}>{note}</p>)}</div></div></section>;
}
