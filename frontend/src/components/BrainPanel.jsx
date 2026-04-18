import React, { useState, useEffect } from 'react'
import axios from 'axios'

const MARKET_COLORS = {
  trending_bull: { color: 'var(--green)', bg: 'var(--green-bg)', label: '📈 Trending Bull' },
  trending_bear: { color: 'var(--red)',   bg: 'var(--red-bg)',   label: '📉 Trending Bear' },
  ranging:       { color: 'var(--amber)', bg: 'var(--amber-bg)', label: '↔ Ranging' },
  mixed:         { color: 'var(--blue)',  bg: 'var(--blue-bg)',  label: '🔀 Mixed' },
}

export default function BrainPanel({ onClose, config={} }) {
  const [log,     setLog]     = useState([])
  const [enabled, setEnabled] = useState(false)
  const [lastRun, setLastRun] = useState('')
  const [running, setRunning] = useState(false)
  const [result,  setResult]  = useState(null)
  const [error,   setError]   = useState('')

  const load = async () => {
    try {
      const r = await axios.get('/api/brain/log', { withCredentials: true })
      setLog(r.data.log || [])
      setEnabled(r.data.enabled)
      setLastRun(r.data.last_run)
    } catch(e) {}
  }

  useEffect(() => { load() }, [])

  const runNow = async () => {
    setRunning(true); setError(''); setResult(null)
    try {
      const r = await axios.post('/api/brain/run', {}, { withCredentials: true })
      if (r.data.ok) {
        setResult(r.data.result)
        await load()
      } else {
        setError(r.data.error || 'Brain returned no result')
      }
    } catch(e) {
      setError(e.response?.data?.error || 'Request failed')
    }
    setRunning(false)
  }

  const toggleBrain = async () => {
    const newVal = !enabled
    setEnabled(newVal)
    await axios.post('/api/settings', { ai_brain_enabled: newVal ? 'true' : 'false' }, { withCredentials: true })
  }

  const hasAnthropicKey = config.anthropic_key_set

  return (
    <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,.78)',display:'flex',alignItems:'center',justifyContent:'center',zIndex:1000}}
      onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div style={{background:'var(--bg-card)',border:'1px solid var(--border)',borderRadius:'var(--radius-lg)',width:580,maxWidth:'96vw',maxHeight:'92vh',display:'flex',flexDirection:'column'}}>

        <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',padding:'16px 20px',borderBottom:'1px solid var(--border)',flexShrink:0}}>
          <div>
            <div style={{fontWeight:600,fontSize:15,display:'flex',alignItems:'center',gap:8}}>
              🧠 AI Brain
              {enabled&&<span style={{fontSize:10,background:'rgba(168,85,247,.15)',border:'1px solid rgba(168,85,247,.3)',borderRadius:10,padding:'2px 8px',color:'#a855f7',fontWeight:600}}>ACTIVE</span>}
            </div>
            <div style={{fontSize:11,color:'var(--text-3)',marginTop:2}}>
              Adaptive strategy engine — analyzes performance and adjusts settings automatically
            </div>
          </div>
          <button onClick={onClose} style={{fontSize:20,color:'var(--text-2)'}}>×</button>
        </div>

        <div style={{flex:1,overflowY:'auto',padding:20}}>

          {/* Enable toggle */}
          <div style={{background:'var(--bg-surface)',border:`1px solid ${enabled?'rgba(168,85,247,.3)':'var(--border)'}`,borderRadius:8,padding:'12px 14px',marginBottom:16}}>
            <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:8}}>
              <span style={{fontSize:13,fontWeight:500}}>Enable AI Brain (auto-adjust every 30 min)</span>
              <div onClick={toggleBrain} style={{width:40,height:22,borderRadius:11,background:enabled?'#a855f7':'var(--border)',cursor:'pointer',position:'relative',transition:'background .2s',flexShrink:0}}>
                <div style={{position:'absolute',top:3,left:enabled?20:3,width:16,height:16,borderRadius:'50%',background:'#fff',transition:'left .2s'}}/>
              </div>
            </div>
            {!hasAnthropicKey&&(
              <div style={{fontSize:11,color:'var(--amber)',background:'var(--amber-bg)',borderRadius:4,padding:'4px 8px'}}>
                ⚠ Requires Anthropic API key — add in Settings → API Keys
              </div>
            )}
          </div>

          {/* How it works */}
          <div style={{background:'var(--blue-bg)',border:'1px solid rgba(59,130,246,.2)',borderRadius:6,padding:'10px 12px',marginBottom:16,fontSize:12,color:'var(--text-2)',lineHeight:1.7}}>
            <b style={{color:'var(--text)'}}>What it does every 30 minutes:</b><br/>
            1. Reads last 24h performance (win rate, P&L, consecutive losses)<br/>
            2. Reads current market conditions from live pair data (no extra API calls)<br/>
            3. Asks Claude Haiku to decide: adjust strategy, tighten/widen SL/TP, pause losing pairs<br/>
            4. Applies changes automatically if confidence is high enough<br/>
            <br/>
            <b style={{color:'var(--text)'}}>Cost:</b> ~$0.003 per cycle × 48 cycles/day = <b style={{color:'var(--green)'}}>~$0.14/day</b> — $20 lasts ~140 days
          </div>

          {/* Run now */}
          <div style={{display:'flex',gap:10,alignItems:'center',marginBottom:16}}>
            <button onClick={runNow} disabled={running||!hasAnthropicKey} style={{
              padding:'8px 20px',borderRadius:6,fontWeight:600,fontSize:12,
              background:!hasAnthropicKey?'var(--border)':'rgba(168,85,247,.15)',
              border:'1px solid rgba(168,85,247,.3)',color:'#a855f7',
              cursor:(!hasAnthropicKey||running)?'not-allowed':'pointer',
              opacity:!hasAnthropicKey?0.5:1,
            }}>
              {running?'🧠 Analyzing...':'🧠 Run brain cycle now'}
            </button>
            {lastRun&&<span style={{fontSize:11,color:'var(--text-3)'}}>Last run: {new Date(lastRun).toLocaleString()}</span>}
          </div>

          {error&&<div style={{background:'var(--red-bg)',border:'1px solid var(--red-dim)',borderRadius:6,padding:'8px 12px',fontSize:12,color:'var(--red)',marginBottom:12}}>{error}</div>}

          {/* Latest result */}
          {result&&<LatestResult result={result}/>}

          {/* Log history */}
          {log.length>0&&<>
            <div style={{fontSize:11,color:'var(--text-3)',textTransform:'uppercase',letterSpacing:.5,marginBottom:8,marginTop:4}}>
              Decision history ({log.length})
            </div>
            {log.map((entry,i)=><LogEntry key={i} entry={entry}/>)}
          </>}

          {log.length===0&&!result&&(
            <div style={{textAlign:'center',padding:32,color:'var(--text-3)',fontSize:13}}>
              No brain cycles run yet. Enable the brain or click "Run now" to start.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function LatestResult({ result }) {
  const mc = MARKET_COLORS[result.market_condition] || MARKET_COLORS.mixed
  return (
    <div style={{background:'rgba(168,85,247,.08)',border:'1px solid rgba(168,85,247,.25)',borderRadius:8,padding:'12px 14px',marginBottom:16}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:8}}>
        <span style={{fontWeight:600,fontSize:13,color:'#a855f7'}}>Latest brain decision</span>
        <div style={{display:'flex',gap:8}}>
          <span style={{fontSize:11,padding:'2px 8px',borderRadius:10,background:mc.bg,color:mc.color,fontWeight:600}}>{mc.label}</span>
          <span style={{fontSize:11,padding:'2px 8px',borderRadius:10,
            background:result.action==='ADJUST'?'var(--amber-bg)':'var(--green-bg)',
            color:result.action==='ADJUST'?'var(--amber)':'var(--green)',fontWeight:600}}>
            {result.action==='ADJUST'?'⚡ Adjusting':'✓ No change needed'}
          </span>
        </div>
      </div>
      <div style={{fontSize:12,color:'var(--text-2)',marginBottom:8,lineHeight:1.6}}>{result.reasoning}</div>
      {result.action==='ADJUST'&&result.adjustments&&Object.keys(result.adjustments).length>0&&(
        <div style={{display:'flex',flexWrap:'wrap',gap:6}}>
          {result.recommended_strategy&&(
            <span style={{fontSize:11,padding:'2px 8px',borderRadius:10,background:'var(--blue-bg)',color:'var(--blue)',fontWeight:500}}>
              Strategy → {result.recommended_strategy}
            </span>
          )}
          {Object.entries(result.adjustments).map(([k,v])=>(
            <span key={k} style={{fontSize:11,padding:'2px 8px',borderRadius:10,background:'var(--bg-hover)',color:'var(--text-2)'}}>
              {k.replace(/_/g,' ')} → {v}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function LogEntry({ entry }) {
  const mc = MARKET_COLORS[entry.market] || MARKET_COLORS.mixed
  const time = new Date(entry.timestamp)
  return (
    <div style={{borderBottom:'1px solid var(--border-dim)',paddingBottom:10,marginBottom:10}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:4}}>
        <span style={{fontSize:11,color:'var(--text-3)'}}>
          {time.toLocaleDateString()} {time.toLocaleTimeString(undefined,{hour:'2-digit',minute:'2-digit'})}
        </span>
        <div style={{display:'flex',gap:6}}>
          <span style={{fontSize:10,padding:'1px 6px',borderRadius:8,background:mc.bg,color:mc.color}}>{mc.label}</span>
          <span style={{fontSize:10,padding:'1px 6px',borderRadius:8,
            background:entry.action==='ADJUST'?'var(--amber-bg)':'var(--green-bg)',
            color:entry.action==='ADJUST'?'var(--amber)':'var(--green)',fontWeight:600}}>
            {entry.action==='ADJUST'?'Adjusted':'No change'}
          </span>
          <span style={{fontSize:10,padding:'1px 6px',borderRadius:8,background:'var(--bg-hover)',color:'var(--text-3)'}}>
            {entry.confidence}% confidence
          </span>
        </div>
      </div>
      <div style={{fontSize:12,color:'var(--text-2)',marginBottom:entry.changes?.length?4:0}}>{entry.reasoning}</div>
      {entry.changes?.length>0&&(
        <div style={{display:'flex',flexWrap:'wrap',gap:4}}>
          {entry.changes.map((c,i)=>(
            <span key={i} style={{fontSize:10,padding:'1px 6px',borderRadius:8,background:'var(--bg-hover)',color:'var(--text-2)'}}>{c}</span>
          ))}
        </div>
      )}
    </div>
  )
}
