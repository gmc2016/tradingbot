import React, { useState } from 'react'
import axios from 'axios'

const POPULAR_PAIRS = ['BTC/USDT','ETH/USDT','BNB/USDT','SOL/USDT','XRP/USDT','ADA/USDT','DOGE/USDT','AVAX/USDT']

export default function ManualTradePanel({ pairs=[], openTrades=[], mode, onClose, onDone }) {
  const [tab,      setTab]      = useState('open')
  const [pair,     setPair]     = useState('BTC/USDT')
  const [side,     setSide]     = useState('BUY')
  const [amount,   setAmount]   = useState('100')
  const [slPct,    setSlPct]    = useState('1.5')
  const [tpPct,    setTpPct]    = useState('3.0')
  const [loading,  setLoading]  = useState(false)
  const [result,   setResult]   = useState(null)
  const [error,    setError]    = useState('')
  const [closing,  setClosing]  = useState(null)

  const currentPrice = pairs.find(p=>p.symbol===pair)?.price || 0

  const handleOpen = async () => {
    setLoading(true); setError(''); setResult(null)
    try {
      const r = await axios.post('/api/trade/manual', {
        pair, side, usdt_amount: parseFloat(amount),
        sl_pct: parseFloat(slPct), tp_pct: parseFloat(tpPct)
      }, { withCredentials: true })
      setResult(r.data.trade)
      onDone()
    } catch(e) {
      setError(e.response?.data?.error || 'Trade failed')
    }
    setLoading(false)
  }

  const handleClose = async (tradeId) => {
    setClosing(tradeId)
    try {
      await axios.post(`/api/trade/close/${tradeId}`, {}, { withCredentials: true })
      onDone()
    } catch(e) {
      setError(e.response?.data?.error || 'Close failed')
    }
    setClosing(null)
  }

  const estSL = currentPrice ? (side==='BUY' ? currentPrice*(1-slPct/100) : currentPrice*(1+slPct/100)).toFixed(4) : '—'
  const estTP = currentPrice ? (side==='BUY' ? currentPrice*(1+tpPct/100) : currentPrice*(1-tpPct/100)).toFixed(4) : '—'
  const estQty= currentPrice && amount ? (parseFloat(amount)/currentPrice).toFixed(6) : '—'

  return (
    <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,.78)',display:'flex',alignItems:'center',justifyContent:'center',zIndex:1000}}
      onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div style={{background:'var(--bg-card)',border:'1px solid var(--border)',borderRadius:'var(--radius-lg)',width:460,maxWidth:'95vw',maxHeight:'90vh',display:'flex',flexDirection:'column'}}>

        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'16px 20px',borderBottom:'1px solid var(--border)',flexShrink:0}}>
          <span style={{fontSize:15,fontWeight:600}}>Manual Trade</span>
          <div style={{display:'flex',alignItems:'center',gap:10}}>
            {mode==='demo'&&<span style={{fontSize:11,background:'var(--blue-bg)',color:'var(--blue)',padding:'2px 8px',borderRadius:10}}>Paper mode</span>}
            {mode==='live'&&<span style={{fontSize:11,background:'var(--red-bg)',color:'var(--red)',padding:'2px 8px',borderRadius:10,fontWeight:600}}>LIVE — real funds</span>}
            <button onClick={onClose} style={{fontSize:20,color:'var(--text-2)'}}>×</button>
          </div>
        </div>

        <div style={{display:'flex',borderBottom:'1px solid var(--border)',flexShrink:0}}>
          {['open','close'].map(t=>(
            <button key={t} onClick={()=>setTab(t)} style={{
              flex:1,padding:'10px',fontSize:12,fontWeight:tab===t?600:400,
              borderBottom:tab===t?'2px solid var(--teal)':'2px solid transparent',
              color:tab===t?'var(--teal)':'var(--text-2)',
            }}>{t==='open'?'Open trade':'Close position'}</button>
          ))}
        </div>

        <div style={{flex:1,overflowY:'auto',padding:20}}>

          {tab==='open'&&<>
            {/* Pair */}
            <div style={{marginBottom:14}}>
              <label style={{fontSize:12,fontWeight:500,display:'block',marginBottom:5}}>Pair</label>
              <select value={pair} onChange={e=>setPair(e.target.value)}>
                {POPULAR_PAIRS.map(p=><option key={p} value={p}>{p}</option>)}
              </select>
              {currentPrice>0&&<div style={{fontSize:11,color:'var(--text-3)',marginTop:4}}>
                Current price: <span style={{color:'var(--text)',fontWeight:500}}>${currentPrice.toLocaleString('en-US',{maximumFractionDigits:4})}</span>
              </div>}
            </div>

            {/* Side */}
            <div style={{marginBottom:14}}>
              <label style={{fontSize:12,fontWeight:500,display:'block',marginBottom:5}}>Direction</label>
              <div style={{display:'flex',gap:8}}>
                {['BUY','SELL'].map(s=>(
                  <button key={s} onClick={()=>setSide(s)} style={{
                    flex:1,padding:'10px',borderRadius:6,fontWeight:600,fontSize:13,
                    border:`1px solid ${side===s?(s==='BUY'?'var(--green-dim)':'var(--red-dim)'):'var(--border)'}`,
                    background:side===s?(s==='BUY'?'var(--green-bg)':'var(--red-bg)'):'transparent',
                    color:side===s?(s==='BUY'?'var(--green)':'var(--red)'):'var(--text-2)',
                  }}>{s==='BUY'?'▲ BUY / LONG':'▼ SELL / SHORT'}</button>
                ))}
              </div>
            </div>

            {/* Amount */}
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:10,marginBottom:14}}>
              <div>
                <label style={{fontSize:12,fontWeight:500,display:'block',marginBottom:5}}>Amount (USDT)</label>
                <input type="number" step="10" value={amount} onChange={e=>setAmount(e.target.value)}/>
              </div>
              <div>
                <label style={{fontSize:12,fontWeight:500,display:'block',marginBottom:5}}>Stop-loss %</label>
                <input type="number" step="0.1" value={slPct} onChange={e=>setSlPct(e.target.value)}/>
              </div>
              <div>
                <label style={{fontSize:12,fontWeight:500,display:'block',marginBottom:5}}>Take-profit %</label>
                <input type="number" step="0.1" value={tpPct} onChange={e=>setTpPct(e.target.value)}/>
              </div>
            </div>

            {/* Preview */}
            <div style={{background:'var(--bg-surface)',border:'1px solid var(--border)',borderRadius:6,padding:'10px 12px',marginBottom:16,fontSize:12}}>
              <div style={{fontWeight:600,marginBottom:8,color:'var(--text-3)',fontSize:10,textTransform:'uppercase'}}>Trade preview</div>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:6}}>
                <Row label="Entry ~" value={currentPrice?`$${currentPrice.toLocaleString('en-US',{maximumFractionDigits:4})}`:'—'}/>
                <Row label="Qty ~" value={estQty}/>
                <Row label="Stop-loss" value={`$${estSL}`} color="var(--red)"/>
                <Row label="Take-profit" value={`$${estTP}`} color="var(--green)"/>
                <Row label="Max loss" value={amount?`$${(parseFloat(amount)*slPct/100).toFixed(2)}`:'—'} color="var(--red)"/>
                <Row label="Target gain" value={amount?`$${(parseFloat(amount)*tpPct/100).toFixed(2)}`:'—'} color="var(--green)"/>
              </div>
            </div>

            {error&&<div style={{background:'var(--red-bg)',border:'1px solid var(--red-dim)',borderRadius:6,padding:'8px 12px',fontSize:12,color:'var(--red)',marginBottom:12}}>{error}</div>}

            {result&&<div style={{background:'var(--green-bg)',border:'1px solid var(--green-dim)',borderRadius:6,padding:'10px 12px',fontSize:12,color:'var(--green)',marginBottom:12}}>
              ✓ Trade opened — {result.side} {result.pair} @ ${result.price?.toFixed(4)} (ID: {result.id})
            </div>}

            <button onClick={handleOpen} disabled={loading} style={{
              width:'100%',padding:'12px',borderRadius:6,fontWeight:600,fontSize:14,
              background:side==='BUY'?'var(--green)':'var(--red)',
              color:'#fff',opacity:loading?0.6:1,cursor:loading?'not-allowed':'pointer',
            }}>
              {loading?'Placing order...':`${side==='BUY'?'▲ Buy':'▼ Sell'} ${pair}`}
            </button>
          </>}

          {tab==='close'&&<>
            {openTrades.length===0?(
              <div style={{textAlign:'center',padding:40,color:'var(--text-3)'}}>No open positions to close</div>
            ):openTrades.map(t=>{
              const pnl=t.unrealized_pnl??t.pnl
              const pc =pnl==null?'var(--text-2)':pnl>=0?'var(--green)':'var(--red)'
              return (
                <div key={t.id} style={{background:'var(--bg-surface)',border:'1px solid var(--border)',borderRadius:6,padding:'12px',marginBottom:10}}>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:8}}>
                    <div>
                      <span style={{fontWeight:600,fontSize:14}}>{t.pair}</span>
                      <span className={`badge badge-${t.side?.toLowerCase()}`} style={{marginLeft:8}}>{t.side}</span>
                    </div>
                    <span style={{fontWeight:700,color:pc,fontSize:14}}>
                      {pnl==null?'—':`${pnl>=0?'+':''}$${pnl.toFixed(2)}`}
                    </span>
                  </div>
                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:4,fontSize:12,marginBottom:10}}>
                    <Row label="Entry" value={`$${t.entry_price?.toFixed(4)}`}/>
                    <Row label="Qty" value={t.quantity?.toFixed(6)}/>
                    <Row label="SL" value={`$${t.stop_loss?.toFixed(4)}`} color="var(--red)"/>
                    <Row label="TP" value={`$${t.take_profit?.toFixed(4)}`} color="var(--green)"/>
                  </div>
                  <button onClick={()=>handleClose(t.id)} disabled={closing===t.id} style={{
                    width:'100%',padding:'8px',borderRadius:6,fontWeight:600,fontSize:12,
                    background:'var(--red-bg)',border:'1px solid var(--red-dim)',color:'var(--red)',
                    opacity:closing===t.id?0.6:1,
                  }}>
                    {closing===t.id?'Closing...':'Close at market price'}
                  </button>
                </div>
              )
            })}
            {error&&<div style={{background:'var(--red-bg)',borderRadius:6,padding:'8px 12px',fontSize:12,color:'var(--red)',marginTop:8}}>{error}</div>}
          </>}
        </div>
      </div>
    </div>
  )
}

function Row({label,value,color}){
  return <div style={{display:'flex',justifyContent:'space-between'}}>
    <span style={{color:'var(--text-3)'}}>{label}</span>
    <span style={{fontWeight:500,color:color||'var(--text)'}}>{value}</span>
  </div>
}
