import React, { useState, useEffect } from 'react'
import axios from 'axios'

const BIAS_STYLE = {
  bullish:          { color:'var(--green)',  bg:'var(--green-bg)',  label:'🟢 Bullish' },
  slightly_bullish: { color:'var(--green)',  bg:'var(--green-bg)',  label:'🟡 Slight Bull' },
  neutral:          { color:'var(--text-2)', bg:'var(--bg-hover)',  label:'⚪ Neutral' },
  caution:          { color:'var(--amber)',  bg:'var(--amber-bg)',  label:'🟠 Caution' },
  bearish:          { color:'var(--red)',    bg:'var(--red-bg)',    label:'🔴 Bearish' },
}

const FG_COLOR = v =>
  v <= 25 ? 'var(--red)' : v <= 45 ? 'var(--amber)' :
  v <= 55 ? 'var(--text-2)' : v <= 75 ? 'var(--green)' : '#f59e0b'

export default function MacroPanel({ onClose }) {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState('')

  const load = async (refresh=false) => {
    setLoading(true); setError('')
    try {
      const r = await axios.get(`/api/macro${refresh?'?refresh=1':''}`, { withCredentials:true })
      setData(r.data)
    } catch(e) { setError(e.response?.data?.error || 'Failed to load macro data') }
    setLoading(false)
  }

  useEffect(()=>{ load() },[])

  const fmt = (v, dec=2) => v!=null ? Number(v).toFixed(dec) : '—'
  const fmtChg = v => v!=null ? `${v>=0?'+':''}${Number(v).toFixed(2)}%` : '—'
  const fmtPrice = (v, dec=2) => v!=null ? Number(v).toLocaleString('en-US',{minimumFractionDigits:dec,maximumFractionDigits:dec}) : '—'

  const signals = data?.signals || {}
  const bias    = BIAS_STYLE[signals.overall_bias] || BIAS_STYLE.neutral
  const fg      = data?.FEAR_GREED
  const dom     = data?.BTC_DOMINANCE

  return (
    <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,.78)',display:'flex',
      alignItems:'center',justifyContent:'center',zIndex:1000}}
      onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div style={{background:'var(--bg-card)',border:'1px solid var(--border)',
        borderRadius:'var(--radius-lg)',width:640,maxWidth:'96vw',maxHeight:'92vh',
        display:'flex',flexDirection:'column'}}>

        {/* Header */}
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',
          padding:'14px 18px',borderBottom:'1px solid var(--border)',flexShrink:0}}>
          <div>
            <div style={{fontWeight:600,fontSize:15}}>🌍 Macro Market Indicators</div>
            <div style={{fontSize:11,color:'var(--text-3)',marginTop:2}}>
              Global markets · Refreshes every 15 min · Influences trade decisions
            </div>
          </div>
          <div style={{display:'flex',gap:8,alignItems:'center'}}>
            <button onClick={()=>load(true)} style={{padding:'4px 12px',border:'1px solid var(--border)',
              borderRadius:6,fontSize:11,color:'var(--text-2)',cursor:'pointer'}}>
              ↻ Refresh
            </button>
            <button onClick={onClose} style={{fontSize:20,color:'var(--text-2)'}}>×</button>
          </div>
        </div>

        <div style={{flex:1,overflowY:'auto',padding:16}}>
          {loading&&<div style={{textAlign:'center',padding:40,color:'var(--text-3)'}}>Loading macro data...</div>}
          {error&&<div style={{background:'var(--red-bg)',borderRadius:6,padding:'8px 12px',color:'var(--red)',fontSize:12,marginBottom:12}}>{error}</div>}

          {data&&<>
            {/* Overall bias + Fear & Greed */}
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:10,marginBottom:16}}>
              <div style={{background:bias.bg,border:`1px solid ${bias.color}33`,
                borderRadius:8,padding:'12px 14px',textAlign:'center'}}>
                <div style={{fontSize:11,color:'var(--text-3)',marginBottom:4}}>Macro Bias</div>
                <div style={{fontSize:18,fontWeight:700,color:bias.color}}>{bias.label}</div>
                <div style={{fontSize:10,color:'var(--text-3)',marginTop:3}}>
                  Position size: {signals.position_mult||1}×
                </div>
              </div>

              {fg&&(
                <div style={{background:'var(--bg-surface)',border:'1px solid var(--border)',
                  borderRadius:8,padding:'12px 14px',textAlign:'center'}}>
                  <div style={{fontSize:11,color:'var(--text-3)',marginBottom:4}}>Fear & Greed</div>
                  <div style={{fontSize:22,fontWeight:700,color:FG_COLOR(fg.value)}}>{fg.value}</div>
                  <div style={{fontSize:11,color:FG_COLOR(fg.value),fontWeight:500}}>{fg.label}</div>
                  {/* Progress bar */}
                  <div style={{height:4,background:'var(--bg-hover)',borderRadius:2,marginTop:6,overflow:'hidden'}}>
                    <div style={{width:`${fg.value}%`,height:'100%',borderRadius:2,
                      background:`linear-gradient(90deg, #ef4444, #f59e0b, #22c55e, #f59e0b, #ef4444)`,
                      backgroundSize:'500px 4px',backgroundPosition:`${fg.value*5}px 0`}}/>
                  </div>
                </div>
              )}

              {dom&&(
                <div style={{background:'var(--bg-surface)',border:'1px solid var(--border)',
                  borderRadius:8,padding:'12px 14px',textAlign:'center'}}>
                  <div style={{fontSize:11,color:'var(--text-3)',marginBottom:4}}>BTC Dominance</div>
                  <div style={{fontSize:22,fontWeight:700,color:'var(--amber)'}}>{dom.btc_dominance}%</div>
                  <div style={{fontSize:11,color:'var(--text-3)'}}>ETH: {dom.eth_dominance}%</div>
                  {signals.alt_season&&(
                    <div style={{fontSize:10,color:'var(--teal)',marginTop:2}}>🌊 Alt season signal</div>
                  )}
                </div>
              )}
            </div>

            {/* Macro suppression warning */}
            {signals.suppress_buy&&(
              <div style={{background:'var(--red-bg)',border:'1px solid var(--red-dim)',
                borderRadius:6,padding:'8px 12px',fontSize:12,color:'var(--red)',
                marginBottom:12,fontWeight:600}}>
                ⚠ BUY signals currently SUPPRESSED by macro conditions
              </div>
            )}

            {/* Macro reasons */}
            {signals.reasons?.length>0&&(
              <div style={{background:'var(--bg-surface)',borderRadius:6,padding:'10px 12px',
                marginBottom:14,fontSize:12,color:'var(--text-2)',lineHeight:1.7}}>
                {signals.reasons.map((r,i)=>(
                  <div key={i}>→ {r}</div>
                ))}
              </div>
            )}

            {/* US Markets */}
            <Section title="🇺🇸 US Stock Markets">
              <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:8}}>
                <MarketCard label="S&P 500" d={data.SP500} bigNum/>
                <MarketCard label="Nasdaq"  d={data.NASDAQ} bigNum/>
                <MarketCard label="Dow Jones" d={data.DOW} bigNum/>
              </div>
            </Section>

            {/* Fear indicators */}
            <Section title="📊 Fear & Volatility">
              <div style={{display:'grid',gridTemplateColumns:'repeat(2,1fr)',gap:8}}>
                <MarketCard label="VIX (Volatility Index)" d={data.VIX}
                  note={data.VIX?.price>35?'🔴 Extreme fear':data.VIX?.price>25?'🟠 Elevated':'🟢 Normal'}/>
                <MarketCard label="US Dollar Index (DXY)" d={data.DXY}
                  note="↑ Strong dollar = crypto headwind"/>
              </div>
            </Section>

            {/* Commodities */}
            <Section title="🛢 Commodities">
              <div style={{display:'grid',gridTemplateColumns:'repeat(2,1fr)',gap:8}}>
                <MarketCard label="Gold (XAU)" d={data.GOLD} prefix="$"/>
                <MarketCard label="Silver (XAG)" d={data.SILVER} prefix="$"/>
                <MarketCard label="Crude Oil WTI" d={data.OIL_WTI} prefix="$"
                  note="↑ Inflation signal → Fed hawkish → risk-off"/>
                <MarketCard label="Brent Crude" d={data.OIL_BRENT} prefix="$"/>
              </div>
            </Section>

            {/* How it influences trading */}
            <Section title="⚙ How This Influences Trading">
              <div style={{fontSize:12,color:'var(--text-2)',lineHeight:1.8}}>
                <div>• <b style={{color:'var(--text)'}}>Position size multiplier {signals.position_mult||1}×</b> — applied to every new trade</div>
                <div>• S&P/Nasdaq down &gt;2% → BUY signals suppressed until macro stabilizes</div>
                <div>• VIX &gt;35 → position size halved (extreme market fear)</div>
                <div>• DXY up &gt;0.5% → headwind for crypto, reduces confidence boost</div>
                <div>• Fear&amp;Greed &lt;20 → contrarian signal, slight BUY confidence boost</div>
                <div>• AI Brain reads full macro context every 30 min to adapt strategy</div>
              </div>
            </Section>

            {data.fetched_at&&(
              <div style={{fontSize:10,color:'var(--text-3)',textAlign:'right'}}>
                Last updated: {new Date(data.fetched_at+'Z').toLocaleTimeString()}
              </div>
            )}
          </>}
        </div>
      </div>
    </div>
  )
}

function Section({title,children}){
  return (
    <div style={{marginBottom:14}}>
      <div style={{fontSize:11,fontWeight:600,color:'var(--text-3)',textTransform:'uppercase',
        letterSpacing:.5,marginBottom:8}}>{title}</div>
      {children}
    </div>
  )
}

function MarketCard({label,d,prefix='',bigNum=false,note}){
  if (!d) return (
    <div style={{background:'var(--bg-surface)',border:'1px solid var(--border)',
      borderRadius:6,padding:'8px 12px',opacity:.5}}>
      <div style={{fontSize:11,color:'var(--text-3)'}}>{label}</div>
      <div style={{fontSize:12,color:'var(--text-3)'}}>—</div>
    </div>
  )
  const isUp = d.change >= 0
  return (
    <div style={{background:'var(--bg-surface)',border:`1px solid ${isUp?'rgba(20,184,166,.2)':'rgba(239,68,68,.2)'}`,
      borderRadius:6,padding:'8px 12px'}}>
      <div style={{fontSize:10,color:'var(--text-3)',marginBottom:3}}>{label}</div>
      <div style={{display:'flex',alignItems:'baseline',gap:6,flexWrap:'wrap'}}>
        <span style={{fontSize:bigNum?14:13,fontWeight:700,fontFamily:'monospace'}}>
          {prefix}{bigNum
            ? Number(d.price).toLocaleString('en-US',{maximumFractionDigits:2})
            : Number(d.price).toFixed(d.price>100?2:4)}
        </span>
        <span style={{fontSize:11,fontWeight:600,color:isUp?'var(--green)':'var(--red)'}}>
          {isUp?'▲':'▼'}{Math.abs(d.change).toFixed(2)}%
        </span>
      </div>
      {note&&<div style={{fontSize:9,color:'var(--text-3)',marginTop:2}}>{note}</div>}
    </div>
  )
}
