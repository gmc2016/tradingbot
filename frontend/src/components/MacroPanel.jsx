import React, { useState, useEffect } from 'react'
import axios from 'axios'

const RISK_COLORS = {
  low:     { color:'var(--green)',  bg:'var(--green-bg)',  label:'✓ Low Risk' },
  medium:  { color:'var(--blue)',   bg:'var(--blue-bg)',   label:'~ Medium Risk' },
  high:    { color:'var(--amber)',  bg:'var(--amber-bg)',  label:'⚠ High Risk' },
  extreme: { color:'var(--red)',    bg:'var(--red-bg)',    label:'✗ Extreme Risk' },
}

const BIAS_COLORS = {
  bullish:  'var(--green)',
  neutral:  'var(--text-2)',
  cautious: 'var(--amber)',
  bearish:  'var(--red)',
}

function MiniBar({ value, max, color }) {
  const pct = Math.min(Math.abs(value / max) * 100, 100)
  return (
    <div style={{flex:1,height:4,background:'var(--bg-hover)',borderRadius:2,overflow:'hidden'}}>
      <div style={{width:`${pct}%`,height:'100%',background:color,borderRadius:2,
        transition:'width .3s'}}/>
    </div>
  )
}

function MacroRow({ label, price, change, unit='', hint }) {
  if (!price && price !== 0) return null
  const isUp = change >= 0
  return (
    <div style={{display:'flex',alignItems:'center',gap:8,padding:'4px 0',
      borderBottom:'1px solid var(--border-dim)'}}>
      <div style={{width:70,fontSize:11,color:'var(--text-3)',flexShrink:0}}>{label}</div>
      <div style={{width:80,fontSize:11,fontFamily:'monospace',fontWeight:600,
        color:'var(--text)',flexShrink:0}}>
        {unit}{typeof price==='number'?price.toLocaleString('en-US',{maximumFractionDigits:2}):price}
      </div>
      <MiniBar value={Math.abs(change)} max={5} color={isUp?'var(--green)':'var(--red)'}/>
      <div style={{width:55,fontSize:10,fontWeight:600,textAlign:'right',flexShrink:0,
        color:isUp?'var(--green)':'var(--red)'}}>
        {isUp?'+':''}{change?.toFixed(2)}%
      </div>
    </div>
  )
}

export default function MacroPanel({ expanded: extExpanded, onToggle }) {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [_expanded,setExpanded]= useState(false)
  const expanded = extExpanded !== undefined ? extExpanded : _expanded

  const load = async () => {
    try {
      const r = await axios.get('/api/macro', { withCredentials: true })
      setData(r.data)
    } catch(e) {}
    setLoading(false)
  }

  useEffect(() => {
    load()
    const interval = setInterval(load, 15 * 60 * 1000) // refresh every 15 min
    return () => clearInterval(interval)
  }, [])

  if (loading && !data) return (
    <div style={{padding:'6px 12px',fontSize:11,color:'var(--text-3)'}}>
      Loading macro indicators...
    </div>
  )
  if (!data) return null

  const { macro={}, risk={} } = data
  const rc = RISK_COLORS[risk.level] || RISK_COLORS.medium
  const fg = macro.FEAR_GREED || {}

  // Fear & Greed color
  const fgColor = fg.value <= 25 ? 'var(--red)' :
                  fg.value <= 45 ? 'var(--amber)' :
                  fg.value <= 65 ? 'var(--text-2)' :
                  fg.value <= 80 ? 'var(--blue)' : 'var(--green)'

  return (
    <div style={{background:'var(--bg-surface)',borderTop:'1px solid var(--border)',flexShrink:0}}>
      {/* Collapsed header — always visible */}
      <div onClick={()=>{ setExpanded(v=>!v); onToggle&&onToggle() }}
        style={{display:'flex',alignItems:'center',gap:10,padding:'5px 12px',
          cursor:'pointer',userSelect:'none'}}
        onMouseEnter={e=>e.currentTarget.style.background='var(--bg-hover)'}
        onMouseLeave={e=>e.currentTarget.style.background='transparent'}>

        <span style={{fontSize:10,fontWeight:600,color:'var(--text-3)',
          textTransform:'uppercase',letterSpacing:.5,flexShrink:0}}>
          Macro
        </span>

        {/* Risk badge */}
        <span style={{fontSize:10,fontWeight:700,padding:'1px 7px',borderRadius:10,
          background:rc.bg,color:rc.color,flexShrink:0}}>
          {rc.label}
        </span>

        {/* Mini ticker strip */}
        <div style={{display:'flex',gap:10,flex:1,overflow:'hidden'}}>
          {[
            ['S&P',   macro.SP500,   '$'],
            ['NQ',    macro.NASDAQ,  '$'],
            ['DJI',   macro.DOW,     '$'],
            ['GOLD',  macro.GOLD,    '$'],
            ['OIL',   macro.OIL,     '$'],
            ['VIX',   macro.VIX,     ''],
          ].map(([label,m,prefix])=>{
            if (!m) return null
            const isUp = (m.change_pct||0) >= 0
            return (
              <div key={label} style={{display:'flex',alignItems:'center',gap:4,flexShrink:0}}>
                <span style={{fontSize:10,color:'var(--text-3)'}}>{label}</span>
                <span style={{fontSize:10,fontWeight:600,color:isUp?'var(--green)':'var(--red)'}}>
                  {isUp?'▲':'▼'}{Math.abs(m.change_pct||0).toFixed(1)}%
                </span>
              </div>
            )
          })}
          {fg.value !== undefined && (
            <div style={{display:'flex',alignItems:'center',gap:4,flexShrink:0}}>
              <span style={{fontSize:10,color:'var(--text-3)'}}>F&G</span>
              <span style={{fontSize:10,fontWeight:700,color:fgColor}}>{fg.value}</span>
            </div>
          )}
        </div>

        {/* Bias */}
        {risk.bias && (
          <span style={{fontSize:10,fontWeight:600,
            color:BIAS_COLORS[risk.bias]||'var(--text-2)',flexShrink:0}}>
            {risk.bias.toUpperCase()}
          </span>
        )}

        <span style={{fontSize:10,color:'var(--text-3)',flexShrink:0}}>
          {expanded?'▲':'▼'}
        </span>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div style={{padding:'8px 12px 12px',borderTop:'1px solid var(--border)'}}>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'0 24px'}}>

            {/* Left column — indices */}
            <div>
              <div style={{fontSize:10,color:'var(--text-3)',textTransform:'uppercase',
                letterSpacing:.5,marginBottom:4,fontWeight:600}}>Stock Indices</div>
              <MacroRow label="S&P 500"  price={macro.SP500?.price}  change={macro.SP500?.change_pct}  unit="$"/>
              <MacroRow label="Nasdaq"   price={macro.NASDAQ?.price} change={macro.NASDAQ?.change_pct} unit="$"/>
              <MacroRow label="Dow Jones"price={macro.DOW?.price}    change={macro.DOW?.change_pct}    unit="$"/>
              <MacroRow label="VIX Fear" price={macro.VIX?.price}    change={macro.VIX?.change_pct}/>
              <div style={{marginTop:8,fontSize:10,color:'var(--text-3)',textTransform:'uppercase',
                letterSpacing:.5,marginBottom:4,fontWeight:600}}>Commodities</div>
              <MacroRow label="Gold"   price={macro.GOLD?.price}   change={macro.GOLD?.change_pct}   unit="$"/>
              <MacroRow label="Silver" price={macro.SILVER?.price} change={macro.SILVER?.change_pct} unit="$"/>
              <MacroRow label="Oil WTI"price={macro.OIL?.price}    change={macro.OIL?.change_pct}    unit="$"/>
            </div>

            {/* Right column — risk + sentiment */}
            <div>
              <div style={{fontSize:10,color:'var(--text-3)',textTransform:'uppercase',
                letterSpacing:.5,marginBottom:4,fontWeight:600}}>Currency & Sentiment</div>
              <MacroRow label="USD Index" price={macro.DXY?.price} change={macro.DXY?.change_pct}/>

              {/* Fear & Greed gauge */}
              {fg.value !== undefined && (
                <div style={{marginTop:8,padding:'8px 10px',background:'var(--bg-card)',
                  borderRadius:6,border:'1px solid var(--border)'}}>
                  <div style={{display:'flex',justifyContent:'space-between',marginBottom:6}}>
                    <span style={{fontSize:11,fontWeight:600}}>Crypto Fear & Greed</span>
                    <span style={{fontSize:13,fontWeight:700,color:fgColor}}>{fg.value}</span>
                  </div>
                  <div style={{height:8,background:'var(--bg-hover)',borderRadius:4,overflow:'hidden',marginBottom:4}}>
                    <div style={{width:`${fg.value}%`,height:'100%',borderRadius:4,
                      background:`linear-gradient(to right, var(--red), var(--amber), var(--green))`}}/>
                  </div>
                  <div style={{display:'flex',justifyContent:'space-between',fontSize:9,color:'var(--text-3)'}}>
                    <span>Extreme Fear</span>
                    <span style={{fontWeight:600,color:fgColor}}>{fg.label}</span>
                    <span>Extreme Greed</span>
                  </div>
                </div>
              )}

              {/* Risk factors */}
              {risk.reasons?.length > 0 && (
                <div style={{marginTop:8}}>
                  <div style={{fontSize:10,color:'var(--text-3)',textTransform:'uppercase',
                    letterSpacing:.5,marginBottom:4,fontWeight:600}}>Active Risk Factors</div>
                  {risk.reasons.map((r,i)=>(
                    <div key={i} style={{fontSize:10,color:'var(--amber)',marginBottom:3,
                      padding:'3px 6px',background:'var(--amber-bg)',borderRadius:3,lineHeight:1.4}}>
                      ⚠ {r}
                    </div>
                  ))}
                </div>
              )}

              {/* Impact on trading */}
              <div style={{marginTop:8,padding:'6px 8px',background:'var(--bg-card)',
                borderRadius:4,border:'1px solid var(--border)',fontSize:10,
                color:'var(--text-2)',lineHeight:1.6}}>
                <b style={{color:'var(--text)'}}>Trading impact:</b><br/>
                {risk.level==='extreme' && '🚫 All new trades blocked — extreme macro risk'}
                {risk.level==='high'    && '⚠ Reduced position size — high macro risk'}
                {risk.level==='medium'  && '~ Normal trading with caution'}
                {risk.level==='low'     && '✓ Favorable conditions for trading'}
              </div>
            </div>
          </div>

          <div style={{marginTop:6,fontSize:10,color:'var(--text-3)',textAlign:'right'}}>
            Updated: {macro.fetched_at ? new Date(macro.fetched_at+'Z').toLocaleTimeString() : '—'}
            {' · '}Refreshes every 15 min
          </div>
        </div>
      )}
    </div>
  )
}
