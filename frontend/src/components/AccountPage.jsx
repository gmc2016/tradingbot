import React, { useState, useEffect } from 'react'
import axios from 'axios'

export default function AccountPage({ onClose }) {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState('')

  const load = async () => {
    setLoading(true); setError('')
    try {
      const r = await axios.get('/api/account', { withCredentials: true })
      setData(r.data)
    } catch(e) {
      setError(e.response?.data?.error || 'Failed to load account data')
    }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  return (
    <div style={{position:'fixed',inset:0,background:'var(--bg-base)',zIndex:500,display:'flex',flexDirection:'column'}}>
      <div style={{height:48,background:'var(--bg-surface)',borderBottom:'1px solid var(--border)',display:'flex',alignItems:'center',justifyContent:'space-between',padding:'0 20px',flexShrink:0}}>
        <div style={{display:'flex',alignItems:'center',gap:16}}>
          <button onClick={onClose} style={{color:'var(--text-2)',fontSize:18}}>←</button>
          <span style={{fontWeight:600,fontSize:15}}>Account & API Status</span>
        </div>
        <button onClick={load} style={{padding:'5px 14px',border:'1px solid var(--border)',borderRadius:6,fontSize:12,color:'var(--text-2)'}}>
          Refresh
        </button>
      </div>

      <div style={{flex:1,overflowY:'auto',padding:'24px 28px',maxWidth:900}}>
        {loading&&<div style={{color:'var(--text-2)',padding:40,textAlign:'center'}}>Loading account data...</div>}
        {error&&<div style={{background:'var(--red-bg)',border:'1px solid var(--red-dim)',borderRadius:6,padding:'10px 14px',color:'var(--red)',marginBottom:16}}>{error}</div>}

        {data&&<>
          {/* Key Status */}
          <Section title="API Key Status">
            <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:12}}>
              <KeyCard name="Binance" set={data.keys?.binance} desc="Required for live trading"/>
              <KeyCard name="NewsAPI" set={data.keys?.newsapi} desc="News sentiment analysis"/>
              <KeyCard name="Anthropic (Claude)" set={data.keys?.anthropic} desc="AI trade filtering" purple/>
            </div>
          </Section>

          {/* Binance Balance */}
          <Section title="Binance Account Balance">
            {data.binance?.error ? (
              <div style={{color:'var(--text-3)',fontSize:13}}>{data.binance.error}</div>
            ) : data.binance ? (
              <>
                <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:12,marginBottom:16}}>
                  <StatCard label="USDT Available" value={`$${(data.binance.usdt_free||0).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}`} color="var(--green)"/>
                  <StatCard label="USDT in Orders" value={`$${(data.binance.usdt_locked||0).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}`} color="var(--amber)"/>
                  <StatCard label="USDT Total" value={`$${(data.binance.usdt_total||0).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}`}/>
                </div>

                {/* Other coin balances */}
                {Object.keys(data.binance.balances||{}).filter(c=>c!=='USDT').length > 0 && (
                  <div>
                    <div style={{fontSize:11,color:'var(--text-3)',textTransform:'uppercase',letterSpacing:.5,marginBottom:8}}>Other holdings</div>
                    <div style={{display:'flex',flexWrap:'wrap',gap:8}}>
                      {Object.entries(data.binance.balances||{})
                        .filter(([coin])=>coin!=='USDT')
                        .map(([coin,bal])=>(
                          <div key={coin} style={{background:'var(--bg-surface)',border:'1px solid var(--border)',borderRadius:6,padding:'6px 12px',fontSize:12}}>
                            <span style={{fontWeight:600}}>{coin}</span>
                            <span style={{color:'var(--text-3)',marginLeft:6}}>{bal.free.toFixed(6)}</span>
                            {bal.used>0&&<span style={{color:'var(--amber)',marginLeft:4}}>({bal.used.toFixed(6)} locked)</span>}
                          </div>
                        ))}
                    </div>
                  </div>
                )}
                {data.binance.fetched_at&&<div style={{fontSize:11,color:'var(--text-3)',marginTop:8}}>Last updated: {new Date(data.binance.fetched_at).toLocaleString()}</div>}
              </>
            ) : (
              <div style={{color:'var(--text-3)',fontSize:13}}>Add Binance API keys in Settings to see balance</div>
            )}
          </Section>

          {/* Anthropic Balance */}
          <Section title="Anthropic API Balance">
            <AnthropicBalance/>
          </Section>

          {/* Claude AI Usage */}
          <Section title="Claude AI Usage">
            {data.llm_stats?.error ? (
              <div style={{color:'var(--text-3)',fontSize:13}}>{data.llm_stats.error}</div>
            ) : (<>
              <div style={{display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:12,marginBottom:12}}>
                <StatCard label="Trades filtered by AI" value={data.llm_stats?.trades_with_llm||0}/>
                <StatCard label="Trades blocked by AI" value={data.llm_stats?.trades_blocked_by_llm||0} color="var(--red)"/>
                <StatCard label="Today's AI calls" value={data.llm_stats?.today||0}/>
                <StatCard label="Est. lifetime cost" value={`$${(data.llm_stats?.estimated_cost_usd||0).toFixed(4)}`} color="var(--green)"/>
              </div>
              <div style={{background:'rgba(168,85,247,.08)',border:'1px solid rgba(168,85,247,.2)',borderRadius:6,padding:'12px 14px',fontSize:12,color:'var(--text-2)',lineHeight:1.8}}>
                <div style={{fontWeight:600,color:'#a855f7',marginBottom:6}}>💡 How to control costs</div>
                <div>• <b style={{color:'var(--text)'}}>Sentiment cache:</b> LLM called max once/hour per pair — uses VADER in between (free)</div>
                <div>• <b style={{color:'var(--text)'}}>Trade filter:</b> Only called when actually opening a trade (not on every signal scan)</div>
                <div>• <b style={{color:'var(--text)'}}>AI Brain:</b> Once every 30 min = ~$0.003 per cycle</div>
                <div>• <b style={{color:'var(--text)'}}>Disable LLM filter</b> in Settings → Strategy to stop trade filter calls entirely</div>
                <div style={{marginTop:6}}>
                  <b style={{color:'var(--text)'}}>Pricing:</b> Haiku · $0.80/M input · $0.20/M output · ~$0.00068/call
                </div>
              </div>
            </>)}
          </Section>

          {/* Mode warning */}
          {data.mode==='demo'&&(
            <div style={{background:'var(--blue-bg)',border:'1px solid rgba(59,130,246,.25)',borderRadius:8,padding:'12px 16px',fontSize:13,color:'var(--text-2)',lineHeight:1.6}}>
              <b style={{color:'var(--blue)'}}>Currently in Demo mode.</b> Binance balance shows your real account balance (if API keys are set) but no real trades are being executed.
              When you switch to Live mode, the bot will use your real USDT balance.
            </div>
          )}
          {data.mode==='live'&&(
            <div style={{background:'var(--red-bg)',border:'1px solid var(--red-dim)',borderRadius:8,padding:'12px 16px',fontSize:13,color:'var(--red)',lineHeight:1.6}}>
              <b>⚠ Currently in LIVE mode.</b> Real orders are being executed on your Binance account.
            </div>
          )}
        </>}
      </div>
    </div>
  )
}

function AnthropicBalance() {
  const [bal, setBal] = React.useState(null)
  const [loading, setLoading] = React.useState(false)

  const check = async () => {
    setLoading(true)
    try {
      const r = await fetch('/api/ai/test', {credentials:'include'})
      const d = await r.json()
      setBal(d)
    } catch(e) { setBal({ok:false,error:'Request failed'}) }
    setLoading(false)
  }

  return (
    <div>
      <div style={{display:'flex',alignItems:'center',gap:12,marginBottom:8}}>
        <button onClick={check} disabled={loading} style={{
          padding:'6px 16px',borderRadius:6,fontSize:12,fontWeight:600,
          background:'rgba(168,85,247,.15)',border:'1px solid rgba(168,85,247,.3)',
          color:'#a855f7',cursor:loading?'not-allowed':'pointer',
        }}>{loading?'Checking...':'🤖 Check Anthropic connection'}</button>
        {bal&&<span style={{fontSize:12,color:bal.ok?'var(--green)':'var(--red)'}}>{bal.ok?'✓ '+bal.message:'✗ '+bal.error}</span>}
      </div>
      <div style={{fontSize:12,color:'var(--text-3)',lineHeight:1.6}}>
        To see your exact credit balance: <a href="https://console.anthropic.com/settings/billing" target="_blank" rel="noreferrer" style={{color:'#a855f7'}}>console.anthropic.com/settings/billing</a>
        <br/>Your balance is visible there under "Credit balance".
      </div>
    </div>
  )
}

function Section({title, children}){
  return <div style={{marginBottom:28}}>
    <div style={{fontSize:13,fontWeight:600,color:'var(--text)',marginBottom:12,paddingBottom:6,borderBottom:'1px solid var(--border)'}}>{title}</div>
    {children}
  </div>
}

function KeyCard({name,set,desc,purple}){
  return <div style={{background:'var(--bg-card)',border:`1px solid ${set?(purple?'rgba(168,85,247,.3)':'var(--green-dim)'):'var(--border)'}`,borderRadius:8,padding:'12px 14px'}}>
    <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:4}}>
      <span style={{fontWeight:600,fontSize:13}}>{name}</span>
      <span style={{fontSize:11,padding:'2px 7px',borderRadius:10,fontWeight:600,
        background:set?(purple?'rgba(168,85,247,.15)':'var(--green-bg)'):'var(--bg-hover)',
        color:set?(purple?'#a855f7':'var(--green)'):'var(--text-3)'}}>
        {set?'✓ Set':'Not set'}
      </span>
    </div>
    <div style={{fontSize:11,color:'var(--text-3)'}}>{desc}</div>
  </div>
}

function StatCard({label,value,color}){
  return <div style={{background:'var(--bg-surface)',border:'1px solid var(--border)',borderRadius:8,padding:'10px 14px'}}>
    <div style={{fontSize:11,color:'var(--text-3)',marginBottom:4}}>{label}</div>
    <div style={{fontSize:20,fontWeight:700,color:color||'var(--text)'}}>{value}</div>
  </div>
}
