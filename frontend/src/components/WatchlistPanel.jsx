import React, { useState, useEffect } from 'react'
import axios from 'axios'

const POPULAR = [
  'BTC/USDT','ETH/USDT','SOL/USDT','BNB/USDT','XRP/USDT',
  'LINK/USDT','AVAX/USDT','DOT/USDT','MATIC/USDT','ADA/USDT',
  'DOGE/USDT','LTC/USDT','ATOM/USDT','UNI/USDT','AAVE/USDT',
  'INJ/USDT','OP/USDT','ARB/USDT','TIA/USDT','SUI/USDT',
]

export default function WatchlistPanel({ onClose, prices={}, onSelectPair }) {
  const [watchlist, setWatchlist] = useState([])
  const [data,      setData]      = useState([])
  const [input,     setInput]     = useState('')
  const [loading,   setLoading]   = useState(true)
  const [saved,     setSaved]     = useState(false)
  const [tab,       setTab]       = useState('list')

  const load = async () => {
    setLoading(true)
    try {
      const r = await axios.get('/api/watchlist', { withCredentials: true })
      setWatchlist(r.data.watchlist || [])
      setData(r.data.pairs || [])
    } catch(e) { console.error(e) }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const save = async (newList) => {
    await axios.post('/api/watchlist', { pairs: newList }, { withCredentials: true })
    setWatchlist(newList)
    setSaved(true); setTimeout(() => setSaved(false), 1500)
    load()
  }

  const addPair = () => {
    let p = input.trim().toUpperCase()
    if (!p) return
    if (!p.includes('/')) p = p + '/USDT'
    if (!watchlist.includes(p)) save([...watchlist, p])
    setInput('')
  }

  const remove = (pair) => save(watchlist.filter(p => p !== pair))

  const fmtP = p =>
    !p ? '—' : p<0.001?p.toFixed(6):p<1?p.toFixed(4):p<100?p.toFixed(2):
    p>=1000?p.toLocaleString('en-US',{maximumFractionDigits:0}):p.toFixed(2)

  return (
    <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,.75)',display:'flex',
      alignItems:'center',justifyContent:'center',zIndex:1000}}
      onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div style={{background:'var(--bg-card)',border:'1px solid var(--border)',
        borderRadius:'var(--radius-lg)',width:520,maxWidth:'95vw',maxHeight:'90vh',
        display:'flex',flexDirection:'column'}}>

        {/* Header */}
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',
          padding:'14px 18px',borderBottom:'1px solid var(--border)',flexShrink:0}}>
          <div>
            <div style={{fontWeight:600,fontSize:15}}>📈 Watchlist</div>
            <div style={{fontSize:11,color:'var(--text-3)',marginTop:2}}>
              Monitored coins — strong signals auto-promote to active trading pairs
            </div>
          </div>
          <button onClick={onClose} style={{fontSize:20,color:'var(--text-2)'}}>×</button>
        </div>

        {/* Tabs */}
        <div style={{display:'flex',borderBottom:'1px solid var(--border)',flexShrink:0}}>
          {[['list','📋 Watchlist'],['add','➕ Add coins']].map(([id,label])=>(
            <button key={id} onClick={()=>setTab(id)} style={{
              padding:'8px 16px',fontSize:12,fontWeight:tab===id?600:400,
              borderBottom:tab===id?'2px solid var(--teal)':'2px solid transparent',
              color:tab===id?'var(--teal)':'var(--text-2)',
            }}>{label}</button>
          ))}
        </div>

        <div style={{flex:1,overflowY:'auto',padding:16}}>

          {/* LIST TAB */}
          {tab==='list'&&<>
            {/* Info box */}
            <div style={{background:'var(--blue-bg)',border:'1px solid rgba(59,130,246,.2)',
              borderRadius:6,padding:'8px 12px',fontSize:11,color:'var(--text-2)',
              lineHeight:1.6,marginBottom:14}}>
              <b style={{color:'var(--text)'}}>How it works:</b> Watchlist coins are analyzed every 5 min.
              If a coin shows a strong signal (≥78% confidence), it's automatically added to active trading pairs.
              The AI Brain also uses watchlist signals for broader market context.
              <br/><span style={{color:'var(--teal)'}}>● Active pair</span>
              <span style={{color:'var(--text-3)',marginLeft:8}}>● Watchlist only</span>
              <span style={{color:'var(--teal)',marginLeft:8}}>↑ Ready to auto-promote</span>
            </div>

            {loading && <div style={{color:'var(--text-3)',fontSize:13,padding:20,textAlign:'center'}}>Loading...</div>}

            {data.map(p => {
              const live   = prices[p.symbol]
              const price  = live?.price  ?? p.price  ?? 0
              const change = live?.change ?? p.change ?? 0
              const isUp   = change >= 0
              const hasSig = p.signal !== 'HOLD' && p.signal !== '--'

              return (
                <div key={p.symbol} style={{
                  display:'flex',alignItems:'center',gap:10,padding:'10px 12px',
                  background:'var(--bg-surface)',borderRadius:6,marginBottom:6,
                  border:`1px solid ${p.auto_promote?'var(--teal)':p.in_active_pairs?'rgba(20,184,166,.2)':'var(--border)'}`,
                }}>
                  {/* Symbol */}
                  <div style={{width:90,flexShrink:0}}>
                    <div style={{fontWeight:600,fontSize:13,cursor:'pointer',color:'var(--text)'}}
                      onClick={()=>{ onSelectPair&&onSelectPair(p.symbol); onClose() }}>
                      {p.symbol.replace('/USDT','')}
                      <span style={{fontSize:9,color:'var(--text-3)'}}>/USDT</span>
                    </div>
                    <div style={{fontSize:10,color:p.in_active_pairs?'var(--teal)':'var(--text-3)'}}>
                      {p.in_active_pairs ? '● trading' : '● watching'}
                    </div>
                  </div>

                  {/* Price */}
                  <div style={{width:80,flexShrink:0}}>
                    <div style={{fontSize:12,fontFamily:'monospace',fontWeight:600}}>{fmtP(price)}</div>
                    <div style={{fontSize:10,color:isUp?'var(--green)':'var(--red)'}}>
                      {isUp?'▲':'▼'}{Math.abs(change).toFixed(2)}%
                    </div>
                  </div>

                  {/* Signal */}
                  <div style={{flex:1}}>
                    {hasSig ? (
                      <div>
                        <span style={{
                          fontSize:10,fontWeight:700,padding:'2px 7px',borderRadius:8,
                          background:p.signal==='BUY'?'var(--green-bg)':'var(--red-bg)',
                          color:p.signal==='BUY'?'var(--green)':'var(--red)',
                        }}>{p.signal} {p.confidence}%</span>
                        {p.auto_promote&&(
                          <span style={{fontSize:10,color:'var(--teal)',marginLeft:6,fontWeight:600}}>
                            ↑ Will auto-promote
                          </span>
                        )}
                      </div>
                    ) : (
                      <span style={{fontSize:10,color:'var(--text-3)'}}>HOLD — monitoring</span>
                    )}
                    {p.reason&&hasSig&&(
                      <div style={{fontSize:10,color:'var(--text-3)',marginTop:2,
                        overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap',maxWidth:180}}>
                        {p.reason}
                      </div>
                    )}
                  </div>

                  {/* Sentiment */}
                  <div style={{width:50,flexShrink:0,textAlign:'center'}}>
                    <div style={{fontSize:10,color:'var(--text-3)'}}>Sentiment</div>
                    <div style={{fontSize:11,fontWeight:600,
                      color:p.sentiment>60?'var(--green)':p.sentiment<40?'var(--red)':'var(--text-2)'}}>
                      {Math.round(p.sentiment||50)}%
                    </div>
                  </div>

                  {/* Remove */}
                  <button onClick={()=>remove(p.symbol)} style={{
                    padding:'3px 8px',borderRadius:4,fontSize:11,flexShrink:0,
                    color:'var(--red)',background:'var(--red-bg)',
                    border:'1px solid var(--red-dim)',cursor:'pointer',
                  }}>✕</button>
                </div>
              )
            })}

            {data.length===0&&!loading&&(
              <div style={{textAlign:'center',padding:30,color:'var(--text-3)',fontSize:13}}>
                No coins in watchlist. Go to "Add coins" tab to add some.
              </div>
            )}
          </>}

          {/* ADD TAB */}
          {tab==='add'&&<>
            {/* Custom input */}
            <div style={{marginBottom:16}}>
              <div style={{fontSize:12,fontWeight:500,marginBottom:6}}>Add any Binance pair</div>
              <div style={{display:'flex',gap:8}}>
                <input value={input} onChange={e=>setInput(e.target.value)}
                  onKeyDown={e=>e.key==='Enter'&&addPair()}
                  placeholder="e.g. INJ or INJ/USDT"
                  style={{flex:1,fontSize:13}}/>
                <button onClick={addPair} style={{
                  padding:'6px 16px',borderRadius:6,background:'var(--teal)',
                  color:'#fff',fontWeight:600,fontSize:12,cursor:'pointer',
                }}>Add</button>
              </div>
            </div>

            {/* Popular coins grid */}
            <div style={{fontSize:11,color:'var(--text-3)',marginBottom:8,textTransform:'uppercase',letterSpacing:.5}}>
              Quick add popular coins
            </div>
            <div style={{display:'flex',flexWrap:'wrap',gap:6}}>
              {POPULAR.map(p=>{
                const inList = watchlist.includes(p)
                return (
                  <button key={p} onClick={()=>!inList&&save([...watchlist,p])} style={{
                    padding:'4px 10px',borderRadius:16,fontSize:11,fontWeight:500,
                    background:inList?'rgba(20,184,166,.15)':'var(--bg-surface)',
                    color:inList?'var(--teal)':'var(--text-2)',
                    border:`1px solid ${inList?'rgba(20,184,166,.3)':'var(--border)'}`,
                    cursor:inList?'default':'pointer',
                  }}>
                    {inList?'✓ ':''}{p.replace('/USDT','')}
                  </button>
                )
              })}
            </div>
          </>}
        </div>

        {/* Footer */}
        <div style={{padding:'10px 16px',borderTop:'1px solid var(--border)',flexShrink:0,
          display:'flex',justifyContent:'space-between',alignItems:'center'}}>
          <span style={{fontSize:11,color:'var(--text-3)'}}>
            {watchlist.length} coins watching · signals checked every 5 min
          </span>
          {saved&&<span style={{fontSize:12,color:'var(--green)'}}>✓ Saved</span>}
          <button onClick={load} style={{
            padding:'5px 14px',border:'1px solid var(--border)',
            borderRadius:6,fontSize:11,color:'var(--text-2)',cursor:'pointer',
          }}>↻ Refresh</button>
        </div>
      </div>
    </div>
  )
}
