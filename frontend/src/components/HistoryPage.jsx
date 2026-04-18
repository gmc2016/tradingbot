import React, { useState, useEffect } from 'react'
import axios from 'axios'

function parseStrategy(reason) {
  if (!reason) return { label: '--', color: 'var(--text-3)', bg: 'var(--bg-hover)' }
  const r = reason.toLowerCase()
  if (r.includes('donchian') && r.includes('confluence'))
    return { label: 'Combined', color: 'var(--teal)', bg: 'rgba(20,184,166,.12)' }
  if (r.includes('donchian'))
    return { label: 'Donchian', color: '#a855f7', bg: 'rgba(168,85,247,.12)' }
  if (r.includes('rsi') || r.includes('macd') || r.includes('bb') || r.includes('ema'))
    return { label: 'RSI/MACD', color: 'var(--blue)', bg: 'var(--blue-bg)' }
  return { label: 'Signal', color: 'var(--text-2)', bg: 'var(--bg-hover)' }
}

function formatPrice(p){ if(!p)return'—'; if(p>1000)return p.toLocaleString('en-US',{maximumFractionDigits:2}); if(p>1)return p.toFixed(4); return p.toFixed(6) }
function formatDate(iso){ if(!iso)return'—'; const d=new Date(iso); return d.toLocaleDateString()+' '+d.toLocaleTimeString(undefined,{hour:'2-digit',minute:'2-digit'}) }

export default function HistoryPage({ onClose }) {
  const [trades,  setTrades]  = useState([])
  const [total,   setTotal]   = useState(0)
  const [page,    setPage]    = useState(1)
  const [filter,  setFilter]  = useState({ status:'', pair:'', strategy:'' })
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo,   setDateTo]   = useState('')
  const [loading, setLoading] = useState(false)
  const perPage = 50

  useEffect(() => { load() }, [page, filter])

  async function load() {
    setLoading(true)
    try {
      const params = { page, per_page: perPage }
      if (filter.status) params.status = filter.status
      if (filter.pair)     params.pair     = filter.pair
      if (filter.strategy) params.strategy = filter.strategy
      if (dateFrom)         params.date_from = dateFrom
      if (dateTo)           params.date_to   = dateTo
      const r = await axios.get('/api/trades/history', { params })
      setTrades(r.data.trades || [])
      setTotal(r.data.total   || 0)
    } catch(e) { console.error(e) }
    setLoading(false)
  }

  const pages   = Math.ceil(total / perPage)
  const winRate = trades.length ? Math.round(trades.filter(t=>t.pnl>0).length/trades.filter(t=>t.status==='closed').length*100)||0 : 0
  const totalPnl = trades.filter(t=>t.status==='closed').reduce((s,t)=>s+(t.pnl||0),0)

  return (
    <div style={{position:'fixed',inset:0,background:'var(--bg-base)',zIndex:500,display:'flex',flexDirection:'column'}}>
      {/* Header */}
      <div style={{height:48,background:'var(--bg-surface)',borderBottom:'1px solid var(--border)',display:'flex',alignItems:'center',justifyContent:'space-between',padding:'0 20px',flexShrink:0}}>
        <div style={{display:'flex',alignItems:'center',gap:16}}>
          <button onClick={onClose} style={{color:'var(--text-2)',fontSize:18,padding:'0 4px'}}>←</button>
          <span style={{fontWeight:600,fontSize:15}}>Trade History</span>
          <span style={{fontSize:12,color:'var(--text-3)'}}>{total} total trades</span>
          <button onClick={()=>window.open('/api/export/trades','_blank')} style={{padding:'4px 12px',border:'1px solid var(--teal)',borderRadius:6,fontSize:11,color:'var(--teal)',background:'rgba(20,184,166,.1)'}}>
            ↓ Export CSV
          </button>
          <button onClick={()=>window.open('/api/export/summary','_blank')} style={{padding:'4px 12px',border:'1px solid rgba(168,85,247,.4)',borderRadius:6,fontSize:11,color:'#a855f7',background:'rgba(168,85,247,.1)'}}>
            🤖 Export for AI review
          </button>
        </div>
        {/* Summary stats */}
        <div style={{display:'flex',gap:20}}>
          {[
            ['Total P&L', `${totalPnl>=0?'+':''}$${totalPnl.toFixed(2)}`, totalPnl>=0?'var(--green)':'var(--red)'],
            ['Win rate',  `${winRate}%`, 'var(--text)'],
          ].map(([l,v,c])=>(
            <div key={l} style={{textAlign:'center'}}>
              <div style={{fontSize:10,color:'var(--text-3)'}}>{l}</div>
              <div style={{fontSize:14,fontWeight:600,color:c}}>{v}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Filters */}
      <div style={{padding:'10px 20px',background:'var(--bg-surface)',borderBottom:'1px solid var(--border)',display:'flex',gap:10,flexShrink:0}}>
        <select value={filter.status} onChange={e=>{ setFilter(f=>({...f,status:e.target.value})); setPage(1) }}
          style={{width:130}}>
          <option value="">All status</option>
          <option value="closed">Closed</option>
          <option value="open">Open</option>
        </select>
        <input placeholder="Filter by pair (e.g. BTC/USDT)" value={filter.pair}
          onChange={e=>{ setFilter(f=>({...f,pair:e.target.value})); setPage(1) }}
          style={{width:220}}/>
        <select value={filter.strategy} onChange={e=>{ setFilter(f=>({...f,strategy:e.target.value})); setPage(1) }}
          style={{width:130}}>
          <option value=''>All strategies</option>
          <option value='donchian'>Donchian</option>
          <option value='rsi'>RSI/MACD</option>
          <option value='combined'>Combined</option>
        </select>
        <input type="date" value={dateFrom} onChange={e=>{setDateFrom(e.target.value);setPage(1)}}
          style={{fontSize:11,padding:'4px 6px',width:130}} title="From date"/>
        <span style={{color:'var(--text-3)',fontSize:11}}>→</span>
        <input type="date" value={dateTo} onChange={e=>{setDateTo(e.target.value);setPage(1)}}
          style={{fontSize:11,padding:'4px 6px',width:130}} title="To date"/>
        <button onClick={()=>{ setFilter({status:'',pair:'',strategy:''}); setDateFrom(''); setDateTo(''); setPage(1) }}
          style={{padding:'6px 14px',border:'1px solid var(--border)',borderRadius:6,color:'var(--text-2)'}}>
          Clear
        </button>
        <span style={{marginLeft:'auto',fontSize:11,color:'var(--text-3)',alignSelf:'center'}}>
          Page {page} of {pages} ({total} trades)
        </span>
      </div>

      {/* Table */}
      <div style={{flex:1,overflow:'auto',padding:'0 20px'}}>
        {loading ? (
          <div style={{display:'flex',alignItems:'center',justifyContent:'center',height:200,color:'var(--text-2)'}}>Loading...</div>
        ) : (
          <table style={{width:'100%',borderCollapse:'collapse',marginTop:8}}>
            <thead>
              <tr style={{borderBottom:'1px solid var(--border)'}}>
                {['Date','Pair','Side','Entry','Exit','Qty','P&L','Status','Strategy','Duration','Reason'].map(h=>(
                  <th key={h} style={{padding:'8px 10px',textAlign:'left',fontSize:11,color:'var(--text-3)',fontWeight:500,position:'sticky',top:0,background:'var(--bg-base)',whiteSpace:'nowrap'}}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trades.length===0?(
                <tr><td colSpan={11} style={{padding:40,textAlign:'center',color:'var(--text-3)'}}>No trades found</td></tr>
              ):trades.map(t=>{
                const pnl      = t.pnl??t.unrealized_pnl
                const isOpen   = t.status==='open'
                const duration = t.opened_at&&t.closed_at
                  ? formatDuration(new Date(t.closed_at)-new Date(t.opened_at))
                  : isOpen ? formatDuration(Date.now()-new Date(t.opened_at)) + ' (open)' : '—'
                return (
                  <tr key={t.id} style={{borderBottom:'1px solid var(--border-dim)'}}
                    onMouseEnter={e=>e.currentTarget.style.background='var(--bg-hover)'}
                    onMouseLeave={e=>e.currentTarget.style.background='transparent'}>
                    <td style={{padding:'7px 10px',color:'var(--text-2)',whiteSpace:'nowrap',fontSize:12}}>{formatDate(t.opened_at)}</td>
                    <td style={{padding:'7px 10px',fontWeight:600}}>{t.pair}</td>
                    <td style={{padding:'7px 10px'}}><span className={`badge badge-${(t.side||'').toLowerCase()}`}>{t.side}</span></td>
                    <td style={{padding:'7px 10px',fontFamily:'monospace',fontSize:12}}>{formatPrice(t.entry_price)}</td>
                    <td style={{padding:'7px 10px',fontFamily:'monospace',fontSize:12,color:'var(--text-2)'}}>{t.exit_price?formatPrice(t.exit_price):'—'}</td>
                    <td style={{padding:'7px 10px',fontFamily:'monospace',fontSize:12,color:'var(--text-2)'}}>{t.quantity?.toFixed(6)}</td>
                    <td style={{padding:'7px 10px',fontWeight:600,color:pnl==null?'var(--text-2)':pnl>=0?'var(--green)':'var(--red)'}}>
                      {pnl==null?'—':`${pnl>=0?'+':''}$${pnl.toFixed(2)}`}
                      {isOpen&&pnl!=null&&<span style={{fontSize:9,marginLeft:3,color:'var(--text-3)'}}>unrlz</span>}
                    </td>
                    <td style={{padding:'7px 10px'}}>
                      <span style={{fontSize:10,padding:'1px 7px',borderRadius:10,fontWeight:500,
                        background:isOpen?'var(--amber-bg)':'var(--bg-hover)',
                        color:isOpen?'var(--amber)':'var(--text-2)'}}>
                        {isOpen?'Open':'Closed'}
                      </span>
                    </td>
                    <td style={{padding:'7px 10px'}}>
                      {(()=>{ const s=parseStrategy(t.strategy_reason); return (
                        <span style={{fontSize:10,padding:'2px 7px',borderRadius:10,fontWeight:600,
                          background:s.bg,color:s.color,whiteSpace:'nowrap'}}>
                          {s.label}
                        </span>
                      )})()}
                    </td>
                    <td style={{padding:'7px 10px',fontSize:11,color:'var(--text-3)',whiteSpace:'nowrap'}}>{duration}</td>
                    <td style={{padding:'7px 10px',color:'var(--text-2)',maxWidth:240,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap',fontSize:12}}>{t.strategy_reason||'—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div style={{padding:'12px 20px',borderTop:'1px solid var(--border)',display:'flex',justifyContent:'center',gap:6,flexShrink:0}}>
          <button onClick={()=>setPage(p=>Math.max(1,p-1))} disabled={page===1}
            style={{padding:'5px 14px',border:'1px solid var(--border)',borderRadius:6,color:'var(--text-2)',opacity:page===1?.4:1}}>← Prev</button>
          {Array.from({length:Math.min(7,pages)},(_,i)=>{
            const p = page<=4 ? i+1 : page+i-3
            if(p<1||p>pages) return null
            return <button key={p} onClick={()=>setPage(p)}
              style={{padding:'5px 12px',border:'1px solid var(--border)',borderRadius:6,
                background:p===page?'var(--teal)':'transparent',
                color:p===page?'#fff':'var(--text-2)',fontWeight:p===page?600:400}}>{p}</button>
          })}
          <button onClick={()=>setPage(p=>Math.min(pages,p+1))} disabled={page===pages}
            style={{padding:'5px 14px',border:'1px solid var(--border)',borderRadius:6,color:'var(--text-2)',opacity:page===pages?.4:1}}>Next →</button>
        </div>
      )}
    </div>
  )
}

function formatDuration(ms){
  const s=Math.floor(ms/1000),m=Math.floor(s/60),h=Math.floor(m/60),d=Math.floor(h/24)
  if(d>0) return `${d}d ${h%24}h`
  if(h>0) return `${h}h ${m%60}m`
  if(m>0) return `${m}m`
  return `${s}s`
}
