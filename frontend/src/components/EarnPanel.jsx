import React, { useState, useEffect } from 'react'
import axios from 'axios'

export default function EarnPanel({ onClose }) {
  const [funding, setFunding]   = useState(null)
  const [earn,    setEarn]      = useState(null)
  const [grid,    setGrid]      = useState(null)
  const [futures, setFutures]   = useState([])
  const [loading, setLoading]   = useState(true)
  const [tab,     setTab]       = useState('overview')

  const load = async () => {
    setLoading(true)
    try {
      const [f, e, g, fu] = await Promise.all([
        axios.get('/api/funding', {withCredentials:true}).catch(()=>({data:{}})),
        axios.get('/api/earn',    {withCredentials:true}).catch(()=>({data:{}})),
        axios.get('/api/grid',    {withCredentials:true}).catch(()=>({data:{}})),
        axios.get('/api/futures/opportunities', {withCredentials:true}).catch(()=>({data:[]})),
      ])
      setFunding(f.data); setEarn(e.data); setGrid(g.data); setFutures(fu.data||[])
    } catch(e) { console.error(e) }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const saveSettings = async (settings) => {
    await axios.post('/api/settings', settings, {withCredentials:true})
    load()
  }

  const fmtPct = v => v != null ? `${v > 0 ? '+':  ''}${parseFloat(v).toFixed(3)}%` : '—'
  const fmtUSD = v => v != null ? `$${parseFloat(v).toFixed(2)}` : '—'

  const tabs = [
    ['overview', '📊 Overview'],
    ['grid',     '⚡ Grid Trading'],
    ['funding',  '💰 Funding Rates'],
    ['futures',  '📈 Futures'],
  ]

  return (
    <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,.8)',
      display:'flex',alignItems:'center',justifyContent:'center',zIndex:1000}}
      onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div style={{background:'var(--bg-card)',border:'1px solid var(--border)',
        borderRadius:'var(--radius-lg)',width:640,maxWidth:'95vw',maxHeight:'90vh',
        display:'flex',flexDirection:'column'}}>

        {/* Header */}
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',
          padding:'14px 18px',borderBottom:'1px solid var(--border)',flexShrink:0}}>
          <div>
            <div style={{fontWeight:600,fontSize:15}}>💹 Binance Features</div>
            <div style={{fontSize:11,color:'var(--text-3)',marginTop:2}}>
              Grid Trading · Funding Rates · Futures · Earn
            </div>
          </div>
          <button onClick={onClose} style={{fontSize:20,color:'var(--text-2)'}}>×</button>
        </div>

        {/* Tabs */}
        <div style={{display:'flex',borderBottom:'1px solid var(--border)',flexShrink:0}}>
          {tabs.map(([id,label])=>(
            <button key={id} onClick={()=>setTab(id)} style={{
              padding:'8px 14px',fontSize:11,fontWeight:tab===id?600:400,
              borderBottom:tab===id?'2px solid var(--teal)':'2px solid transparent',
              color:tab===id?'var(--teal)':'var(--text-2)',
            }}>{label}</button>
          ))}
        </div>

        <div style={{flex:1,overflowY:'auto',padding:16}}>
          {loading && <div style={{textAlign:'center',padding:30,color:'var(--text-3)'}}>Loading...</div>}

          {/* OVERVIEW TAB */}
          {!loading && tab==='overview' && (
            <div>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10,marginBottom:16}}>
                {/* Funding Rate card */}
                <div style={{padding:14,background:'var(--bg-surface)',borderRadius:8,
                  border:'1px solid var(--border)'}}>
                  <div style={{fontSize:11,color:'var(--text-3)',marginBottom:4}}>💰 Best Funding Rate</div>
                  {funding?.best_pair ? <>
                    <div style={{fontSize:16,fontWeight:700,color:'var(--green)'}}>
                      {fmtPct(funding.best_rate)}/8h
                    </div>
                    <div style={{fontSize:11,color:'var(--text-2)'}}>{funding.best_pair}</div>
                    <div style={{fontSize:10,color:'var(--text-3)',marginTop:4}}>
                      ≈ {fmtPct(funding.best_daily)}/day · {funding.best_annual?.toFixed(0)}% APY
                    </div>
                  </> : <div style={{fontSize:11,color:'var(--text-3)'}}>Loading...</div>}
                </div>

                {/* Earn card */}
                <div style={{padding:14,background:'var(--bg-surface)',borderRadius:8,
                  border:'1px solid var(--border)'}}>
                  <div style={{fontSize:11,color:'var(--text-3)',marginBottom:4}}>🏦 Idle Capital Earn</div>
                  {earn?.idle_capital > 0 ? <>
                    <div style={{fontSize:16,fontWeight:700,color:'var(--blue)'}}>
                      {earn.apy?.toFixed(1)}% APY
                    </div>
                    <div style={{fontSize:11,color:'var(--text-2)'}}>
                      On ${earn.idle_capital?.toFixed(0)} idle capital
                    </div>
                    <div style={{fontSize:10,color:'var(--text-3)',marginTop:4}}>
                      ≈ ${earn.daily_income?.toFixed(4)}/day · ${earn.monthly_income?.toFixed(2)}/month
                    </div>
                  </> : <div style={{fontSize:11,color:'var(--text-3)'}}>All capital deployed</div>}
                </div>

                {/* Grid card */}
                <div style={{padding:14,background:'var(--bg-surface)',borderRadius:8,
                  border:`1px solid ${grid?.config?.enabled?'var(--teal)':'var(--border)'}`}}>
                  <div style={{fontSize:11,color:'var(--text-3)',marginBottom:4}}>⚡ Grid Trading</div>
                  <div style={{fontSize:13,fontWeight:600,
                    color:grid?.config?.enabled?'var(--teal)':'var(--text-3)'}}>
                    {grid?.config?.enabled ? '● Active' : '○ Inactive'}
                  </div>
                  {grid?.state?.total_pnl != null && (
                    <div style={{fontSize:11,color:'var(--text-2)',marginTop:4}}>
                      PnL: ${grid.state.total_pnl?.toFixed(2)} | {grid.state.fills||0} fills
                    </div>
                  )}
                  <div style={{fontSize:10,color:'var(--text-3)',marginTop:2}}>
                    {grid?.config?.pair} · ${grid?.config?.capital} · {grid?.config?.num_levels} levels
                  </div>
                </div>

                {/* Futures card */}
                <div style={{padding:14,background:'var(--bg-surface)',borderRadius:8,
                  border:'1px solid var(--border)'}}>
                  <div style={{fontSize:11,color:'var(--text-3)',marginBottom:4}}>📈 Futures Amplifier</div>
                  <div style={{fontSize:13,fontWeight:600,color:'var(--amber)'}}>2x Leverage</div>
                  <div style={{fontSize:11,color:'var(--text-2)',marginTop:4}}>
                    On signals ≥80% confidence
                  </div>
                  <div style={{fontSize:10,color:'var(--text-3)',marginTop:2}}>
                    BTC/ETH only · $50/position
                  </div>
                </div>
              </div>

              {/* Combined daily estimate */}
              <div style={{padding:14,background:'var(--blue-bg)',borderRadius:8,
                border:'1px solid rgba(59,130,246,.2)'}}>
                <div style={{fontSize:12,fontWeight:600,marginBottom:8}}>
                  💡 Combined passive income estimate
                </div>
                <div style={{display:'flex',gap:16,flexWrap:'wrap'}}>
                  {[
                    ['Funding rate (BTC)', `$${((funding?.btc_rate||0)*3*1000/100).toFixed(2)}/day`, 'on $1000 hedge'],
                    ['Earn (idle $400)', `$${(earn?.daily_income||0).toFixed(3)}/day`, `${earn?.apy?.toFixed(1)||4.5}% APY`],
                    ['Grid (ranging)', '$1-5/day', 'during flat markets'],
                  ].map(([label,val,sub])=>(
                    <div key={label}>
                      <div style={{fontSize:10,color:'var(--text-3)'}}>{label}</div>
                      <div style={{fontSize:13,fontWeight:600,color:'var(--green)'}}>{val}</div>
                      <div style={{fontSize:10,color:'var(--text-3)'}}>{sub}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* GRID TAB */}
          {!loading && tab==='grid' && (
            <div>
              <div style={{background:'var(--bg-surface)',borderRadius:8,padding:12,
                marginBottom:12,fontSize:11,color:'var(--text-2)',lineHeight:1.7}}>
                <b style={{color:'var(--text)'}}>How Grid Trading works:</b> Places buy orders below 
                current price and sell orders above at regular intervals. Every time price bounces 
                within the range, profit is captured. Best during sideways/ranging markets — 
                exactly when the directional bot is inactive.
              </div>

              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10,marginBottom:12}}>
                {[
                  ['Pair', grid?.config?.pair || 'BTC/USDT', 'grid_pair'],
                  ['Capital ($)', grid?.config?.capital || '200', 'grid_capital'],
                  ['Grid levels', grid?.config?.num_levels || '10', 'grid_levels'],
                  ['Price range (%)', grid?.config?.range_pct || '4.0', 'grid_range_pct'],
                ].map(([label, val, key])=>(
                  <div key={key}>
                    <div style={{fontSize:11,color:'var(--text-3)',marginBottom:4}}>{label}</div>
                    <input defaultValue={val} style={{width:'100%',fontSize:12}}
                      onBlur={e=>saveSettings({[key]:e.target.value})}/>
                  </div>
                ))}
              </div>

              <div style={{display:'flex',gap:8,marginBottom:12}}>
                <button onClick={()=>saveSettings({grid_enabled: grid?.config?.enabled?'false':'true'})}
                  style={{padding:'8px 16px',borderRadius:6,fontWeight:600,fontSize:12,cursor:'pointer',
                    background:grid?.config?.enabled?'var(--red)':'var(--green)',color:'#fff',border:'none'}}>
                  {grid?.config?.enabled ? 'Stop Grid' : 'Start Grid'}
                </button>
                <button onClick={async()=>{
                  await axios.post('/api/grid/reset',{},{withCredentials:true}); load()
                }} style={{padding:'8px 16px',borderRadius:6,fontSize:12,cursor:'pointer',
                  border:'1px solid var(--border)',color:'var(--text-2)'}}>
                  Reset Grid
                </button>
              </div>

              {grid?.state?.total_pnl != null && (
                <div style={{padding:12,background:'var(--bg-surface)',borderRadius:8}}>
                  <div style={{fontSize:12,fontWeight:600,marginBottom:8}}>Grid Performance</div>
                  <div style={{display:'flex',gap:16}}>
                    <div>
                      <div style={{fontSize:10,color:'var(--text-3)'}}>Total PnL</div>
                      <div style={{fontSize:14,fontWeight:700,
                        color:(grid.state.total_pnl||0)>=0?'var(--green)':'var(--red)'}}>
                        ${(grid.state.total_pnl||0).toFixed(2)}
                      </div>
                    </div>
                    <div>
                      <div style={{fontSize:10,color:'var(--text-3)'}}>Fills</div>
                      <div style={{fontSize:14,fontWeight:700}}>{grid.state.fills||0}</div>
                    </div>
                    <div>
                      <div style={{fontSize:10,color:'var(--text-3)'}}>Range</div>
                      <div style={{fontSize:11,color:'var(--text-2)'}}>
                        ${grid.state.lower?.toFixed(0)}-${grid.state.upper?.toFixed(0)}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* FUNDING TAB */}
          {!loading && tab==='funding' && (
            <div>
              <div style={{background:'var(--bg-surface)',borderRadius:8,padding:12,
                marginBottom:12,fontSize:11,color:'var(--text-2)',lineHeight:1.7}}>
                <b style={{color:'var(--text)'}}>Funding Rate Harvesting:</b> When traders heavily buy 
                futures (positive funding rate), longs pay shorts every 8 hours. You buy spot BTC + 
                short BTC futures simultaneously — delta neutral, no price risk. You just collect 
                the payment. During bull markets this can be 0.05-0.1% per 8h = 0.15-0.3%/day.
              </div>

              {/* BTC/ETH rates */}
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10,marginBottom:12}}>
                {[['BTC', funding?.btc_rate], ['ETH', funding?.eth_rate]].map(([coin, rate])=>(
                  <div key={coin} style={{padding:12,background:'var(--bg-surface)',borderRadius:8,
                    border:'1px solid var(--border)'}}>
                    <div style={{fontSize:12,fontWeight:600}}>{coin}/USDT Futures</div>
                    <div style={{fontSize:18,fontWeight:700,
                      color:(rate||0)>0?'var(--green)':'var(--red)'}}>
                      {fmtPct(rate)}/8h
                    </div>
                    <div style={{fontSize:10,color:'var(--text-3)',marginTop:4}}>
                      {((rate||0)*3).toFixed(3)}%/day · {((rate||0)*3*365).toFixed(1)}% APY
                      <br/>On $500: ${((500*(rate||0)*3)/100).toFixed(3)}/day
                    </div>
                  </div>
                ))}
              </div>

              {/* Top opportunities */}
              <div style={{fontSize:12,fontWeight:600,marginBottom:8}}>Top Funding Opportunities</div>
              {(funding?.opportunities||[]).slice(0,5).map((o,i)=>(
                <div key={i} style={{display:'flex',justifyContent:'space-between',
                  alignItems:'center',padding:'8px 10px',
                  background:'var(--bg-surface)',borderRadius:6,marginBottom:4}}>
                  <span style={{fontSize:12,fontWeight:500}}>{o.pair}</span>
                  <span style={{fontSize:12,fontWeight:600,
                    color:o.rate>0?'var(--green)':'var(--red)'}}>
                    {fmtPct(o.rate_pct)}/8h
                  </span>
                  <span style={{fontSize:11,color:'var(--text-3)'}}>
                    {o.annualized?.toFixed(0)}% APY
                  </span>
                  <span style={{fontSize:10,padding:'2px 6px',borderRadius:6,
                    background:o.rate>0?'var(--green-bg)':'var(--red-bg)',
                    color:o.rate>0?'var(--green)':'var(--red)'}}>
                    {o.direction==='short_futures'?'Short futures':'Long futures'}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* FUTURES TAB */}
          {!loading && tab==='futures' && (
            <div>
              <div style={{background:'var(--bg-surface)',borderRadius:8,padding:12,
                marginBottom:12,fontSize:11,color:'var(--text-2)',lineHeight:1.7}}>
                <b style={{color:'var(--text)'}}>Futures Amplifier:</b> When the spot bot sees a 
                high-confidence signal (≥80%), it ALSO opens a leveraged futures position in the 
                same direction. 2x leverage means: spot makes $1, futures makes $2 additional. 
                Total: 3x your normal profit on the best signals. Tighter SL to manage leverage risk.
              </div>

              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10,marginBottom:12}}>
                {[
                  ['Leverage', '2', 'futures_leverage', 'Max 3x recommended'],
                  ['Min confidence %', '80', 'futures_min_conf', 'Only highest quality signals'],
                  ['Position size $', '50', 'futures_size', 'Per futures trade'],
                ].map(([label,val,key,hint])=>(
                  <div key={key}>
                    <div style={{fontSize:11,color:'var(--text-3)',marginBottom:4}}>{label}</div>
                    <input defaultValue={val} style={{width:'100%',fontSize:12}}
                      onBlur={e=>saveSettings({[key]:e.target.value})}/>
                    <div style={{fontSize:10,color:'var(--text-3)',marginTop:2}}>{hint}</div>
                  </div>
                ))}
              </div>

              <div style={{padding:12,background:'var(--amber-bg)',borderRadius:8,
                border:'1px solid rgba(245,158,11,.3)',fontSize:11,color:'var(--text-2)'}}>
                ⚠️ <b>Demo mode:</b> Futures positions tracked mathematically. 
                Enable in live mode only when spot trading is consistently profitable.
                Start with 2x leverage maximum.
              </div>

              {futures.length > 0 && (
                <div style={{marginTop:12}}>
                  <div style={{fontSize:12,fontWeight:600,marginBottom:8}}>Futures Market Data</div>
                  {futures.map((f,i)=>(
                    <div key={i} style={{display:'flex',justifyContent:'space-between',
                      padding:'6px 10px',background:'var(--bg-surface)',borderRadius:6,marginBottom:4}}>
                      <span style={{fontSize:12,fontWeight:500}}>{f.pair}</span>
                      <span style={{fontSize:12,fontFamily:'monospace'}}>${f.price?.toFixed(2)}</span>
                      <span style={{fontSize:11,
                        color:(f.change_pct||0)>=0?'var(--green)':'var(--red)'}}>
                        {(f.change_pct||0)>=0?'+':''}{f.change_pct?.toFixed(2)}%
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div style={{padding:'10px 16px',borderTop:'1px solid var(--border)',flexShrink:0,
          display:'flex',justifyContent:'space-between',alignItems:'center'}}>
          <span style={{fontSize:11,color:'var(--text-3)'}}>
            All features available in demo · Goes live with your Binance API key
          </span>
          <button onClick={load} style={{padding:'5px 14px',border:'1px solid var(--border)',
            borderRadius:6,fontSize:11,color:'var(--text-2)',cursor:'pointer'}}>
            ↻ Refresh
          </button>
        </div>
      </div>
    </div>
  )
}
