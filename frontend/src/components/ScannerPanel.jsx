import React, { useState, useEffect } from 'react'
import axios from 'axios'

export default function ScannerPanel({ onClose, config={}, onPairsUpdated }) {
  const [loading,    setLoading]    = useState(false)
  const [result,     setResult]     = useState(null)
  const [lastScan,   setLastScan]   = useState(null)
  const [autoUpdate, setAutoUpdate] = useState(config.scanner_auto_update !== 'false')
  const [error,      setError]      = useState('')

  useEffect(() => {
    axios.get('/api/scanner/last', { withCredentials: true })
      .then(r => { if (r.data.result) setLastScan(r.data.result) })
      .catch(() => {})
  }, [])

  const runScan = async () => {
    setLoading(true); setError(''); setResult(null)
    try {
      const r = await axios.post('/api/scanner/run',
        { auto_update: autoUpdate }, { withCredentials: true })
      setResult(r.data.result)
      if (autoUpdate && onPairsUpdated) onPairsUpdated(r.data.active_pairs)
    } catch(e) {
      setError(e.response?.data?.error || 'Scan failed')
    }
    setLoading(false)
  }

  const displayResult = result || lastScan

  return (
    <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,.78)',display:'flex',alignItems:'center',justifyContent:'center',zIndex:1000}}
      onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div style={{background:'var(--bg-card)',border:'1px solid var(--border)',borderRadius:'var(--radius-lg)',width:560,maxWidth:'96vw',maxHeight:'90vh',display:'flex',flexDirection:'column'}}>

        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'16px 20px',borderBottom:'1px solid var(--border)',flexShrink:0}}>
          <div>
            <div style={{fontWeight:600,fontSize:15}}>🔍 Smart Pair Scanner</div>
            <div style={{fontSize:11,color:'var(--text-3)',marginTop:2}}>
              Scans all Binance USDT pairs and finds the best ones to trade
            </div>
          </div>
          <button onClick={onClose} style={{fontSize:20,color:'var(--text-2)'}}>×</button>
        </div>

        <div style={{flex:1,overflowY:'auto',padding:20}}>

          {/* Options */}
          <div style={{background:'var(--bg-surface)',border:'1px solid var(--border)',borderRadius:8,padding:'12px 14px',marginBottom:16}}>
            <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:8}}>
              <span style={{fontSize:12,fontWeight:500}}>Auto-update active pairs after scan</span>
              <div onClick={()=>setAutoUpdate(v=>!v)} style={{width:36,height:20,borderRadius:10,background:autoUpdate?'var(--teal)':'var(--border)',cursor:'pointer',position:'relative',transition:'background .2s',flexShrink:0}}>
                <div style={{position:'absolute',top:2,left:autoUpdate?18:2,width:16,height:16,borderRadius:'50%',background:'#fff',transition:'left .2s'}}/>
              </div>
            </div>
            <div style={{fontSize:11,color:'var(--text-3)',lineHeight:1.5}}>
              When ON: scanner replaces your active pairs list with the best found pairs
              (keeping any pinned pairs). When OFF: results are shown but pairs not changed.
            </div>
          </div>

          {/* Info */}
          <div style={{background:'var(--blue-bg)',border:'1px solid rgba(59,130,246,.2)',borderRadius:6,padding:'10px 12px',marginBottom:16,fontSize:12,color:'var(--text-2)',lineHeight:1.6}}>
            <b style={{color:'var(--text)'}}>How it works:</b><br/>
            1. Fetches all USDT pairs from Binance with 24h volume &gt; $1M<br/>
            2. Scores each by volatility, volume, ADX trend strength, ATR<br/>
            3. If Anthropic key is set: Claude AI ranks the top 20 candidates and picks the best 8<br/>
            4. Result: a curated list of pairs with best trading conditions right now<br/>
            <br/>
            <b style={{color:'var(--text)'}}>Runs automatically every 6 hours</b> when scanner is enabled.
            {config.last_scan_at && <span style={{color:'var(--text-3)'}}> Last ran: {new Date(config.last_scan_at).toLocaleString()}</span>}
          </div>

          {error && (
            <div style={{background:'var(--red-bg)',border:'1px solid var(--red-dim)',borderRadius:6,padding:'8px 12px',fontSize:12,color:'var(--red)',marginBottom:12}}>{error}</div>
          )}

          {/* Run button */}
          <button onClick={runScan} disabled={loading} style={{
            width:'100%',padding:'11px',borderRadius:6,fontWeight:600,fontSize:14,
            background:loading?'var(--border)':'var(--teal)',color:'#fff',
            cursor:loading?'not-allowed':'pointer',marginBottom:20,
          }}>
            {loading ? (
              <span>🔍 Scanning {Math.floor(Math.random()*400)+100} pairs... this takes ~30 seconds</span>
            ) : '🔍 Run scan now'}
          </button>

          {/* Results */}
          {displayResult && (
            <div>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:10}}>
                <div style={{fontWeight:600,fontSize:13}}>
                  {result ? 'Latest scan results' : 'Previous scan results'}
                </div>
                <div style={{display:'flex',alignItems:'center',gap:8}}>
                  <span style={{fontSize:11,color:'var(--text-3)'}}>
                    Scanned {displayResult.total_scanned} pairs
                  </span>
                  <span style={{fontSize:10,padding:'2px 7px',borderRadius:10,fontWeight:600,
                    background:displayResult.method==='ai'?'rgba(168,85,247,.15)':'var(--blue-bg)',
                    color:displayResult.method==='ai'?'#a855f7':'var(--blue)'}}>
                    {displayResult.method==='ai'?'🤖 AI ranked':'📊 Technical'}
                  </span>
                </div>
              </div>

              {displayResult.summary && (
                <div style={{background:'var(--bg-surface)',borderRadius:6,padding:'8px 12px',fontSize:12,color:'var(--text-2)',marginBottom:12,lineHeight:1.5,fontStyle:'italic'}}>
                  "{displayResult.summary}"
                </div>
              )}

              {/* Selected pairs */}
              <div style={{marginBottom:12}}>
                <div style={{fontSize:11,color:'var(--text-3)',textTransform:'uppercase',letterSpacing:.5,marginBottom:6}}>
                  Selected pairs ({displayResult.selected?.length || 0})
                </div>
                <div style={{display:'flex',flexWrap:'wrap',gap:6}}>
                  {(displayResult.selected || []).map(sym => (
                    <span key={sym} style={{
                      padding:'4px 10px',borderRadius:20,fontSize:12,fontWeight:600,
                      background:'rgba(20,184,166,.12)',border:'1px solid rgba(20,184,166,.3)',color:'var(--teal)',
                    }}>{sym}</span>
                  ))}
                </div>
              </div>

              {/* LLM rankings with reasons */}
              {displayResult.llm_rankings && (
                <div>
                  <div style={{fontSize:11,color:'var(--text-3)',textTransform:'uppercase',letterSpacing:.5,marginBottom:6}}>AI analysis</div>
                  {displayResult.llm_rankings.map((p,i) => (
                    <div key={p.symbol} style={{
                      display:'flex',alignItems:'flex-start',gap:10,padding:'7px 10px',
                      background:i%2===0?'var(--bg-surface)':'transparent',borderRadius:4,marginBottom:2,
                    }}>
                      <span style={{fontSize:11,color:'var(--text-3)',width:20,flexShrink:0,paddingTop:1}}>#{i+1}</span>
                      <span style={{fontWeight:600,fontSize:12,width:90,flexShrink:0}}>{p.symbol}</span>
                      <div style={{flex:1}}>
                        <div style={{height:4,background:'var(--bg-hover)',borderRadius:2,marginBottom:3,overflow:'hidden'}}>
                          <div style={{width:`${p.score}%`,height:'100%',background:'var(--teal)',borderRadius:2}}/>
                        </div>
                        <span style={{fontSize:11,color:'var(--text-2)'}}>{p.reason}</span>
                      </div>
                      <span style={{fontSize:11,fontWeight:600,color:'var(--teal)',width:30,textAlign:'right',flexShrink:0}}>{p.score}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Technical top candidates (no LLM) */}
              {!displayResult.llm_rankings && displayResult.candidates && (
                <div>
                  <div style={{fontSize:11,color:'var(--text-3)',textTransform:'uppercase',letterSpacing:.5,marginBottom:6}}>Top candidates by technical score</div>
                  {displayResult.candidates.slice(0,10).map((c,i) => (
                    <div key={c.symbol} style={{
                      display:'flex',alignItems:'center',gap:10,padding:'5px 8px',
                      background:i%2===0?'var(--bg-surface)':'transparent',borderRadius:4,marginBottom:2,fontSize:12,
                    }}>
                      <span style={{color:'var(--text-3)',width:20}}>#{i+1}</span>
                      <span style={{fontWeight:600,width:100}}>{c.symbol}</span>
                      <span style={{color:c.change_24h>=0?'var(--green)':'var(--red)',width:60}}>{c.change_24h>=0?'+':''}{c.change_24h}%</span>
                      <div style={{flex:1,height:4,background:'var(--bg-hover)',borderRadius:2,overflow:'hidden'}}>
                        <div style={{width:`${c.tech_score}%`,height:'100%',background:'var(--blue)',borderRadius:2}}/>
                      </div>
                      <span style={{color:'var(--text-3)',width:30,textAlign:'right'}}>{c.tech_score}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
