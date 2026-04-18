import React, { useState, useEffect } from 'react'
import axios from 'axios'

export default function SettingsModal({ config={}, onSave, onClose, onLogout, username }) {
  const [tab, setTab] = useState('strategy')
  const [f, setF] = useState({
    stop_loss_pct:'1.5', take_profit_pct:'3.0', position_size_usdt:'100',
    max_positions:'5', active_pairs:'BTC/USDT,ETH/USDT,BNB/USDT,SOL/USDT,XRP/USDT,ADA/USDT,DOGE/USDT,AVAX/USDT',
    starting_balance:'1000', strategy_mode:'combined',
    trailing_stop_enabled:'true', trailing_stop_pct:'0.8',
    partial_close_enabled:'true', partial_close_at_pct:'1.5', partial_close_size_pct:'50',
    max_loss_streak:'3', cooldown_minutes:'60',
    binance_api_key:'', binance_api_secret:'', newsapi_key:'', anthropic_api_key:'',
    scanner_enabled:'true', scanner_auto_update:'true', scanner_top_n:'8', pinned_pairs:'BTC/USDT,ETH/USDT',
  })
  const [showSecrets,  setShowSecrets]  = useState(false)
  const [saved,        setSaved]        = useState(false)
  const [newPass,      setNewPass]      = useState('')
  const [passSaved,    setPassSaved]    = useState(false)
  const [aiTest,       setAiTest]       = useState('')
  const [passError,    setPassError]    = useState('')
  const [resetDone,    setResetDone]    = useState(false)
  const [resetError,   setResetError]   = useState('')

  const loadSettings = async () => {
    try {
      const r  = await axios.get('/api/settings', { withCredentials: true })
      const s  = r.data
      const ap = Array.isArray(s.active_pairs) ? s.active_pairs.join(',') : (s.active_pairs||'')
      setF(prev => ({
        ...prev,
        // Strategy & AI
        strategy_mode:           s.strategy_mode          || prev.strategy_mode,
        use_llm_filter:          s.use_llm_filter         || 'false',
        mtf_enabled:             s.mtf_enabled            || 'false',
        max_loss_streak:         s.max_loss_streak        || prev.max_loss_streak,
        cooldown_minutes:        s.cooldown_minutes       || prev.cooldown_minutes,
        // Risk
        stop_loss_pct:           s.stop_loss_pct          || prev.stop_loss_pct,
        take_profit_pct:         s.take_profit_pct        || prev.take_profit_pct,
        position_size_usdt:      s.position_size_usdt     || prev.position_size_usdt,
        max_positions:           s.max_positions          || prev.max_positions,
        starting_balance:        s.starting_balance       || prev.starting_balance,
        // Profit
        trailing_stop_enabled:   s.trailing_stop_enabled  || 'false',
        trailing_stop_pct:       s.trailing_stop_pct      || prev.trailing_stop_pct,
        partial_close_enabled:   s.partial_close_enabled  || 'false',
        partial_close_at_pct:    s.partial_close_at_pct   || prev.partial_close_at_pct,
        partial_close_size_pct:  s.partial_close_size_pct || prev.partial_close_size_pct,
        // Scanner
        scanner_enabled:         s.scanner_enabled        || 'false',
        scanner_auto_update:     s.scanner_auto_update    || 'false',
        scanner_top_n:           s.scanner_top_n          || prev.scanner_top_n,
        pinned_pairs:            s.pinned_pairs           || prev.pinned_pairs,
        // Pairs
        active_pairs:            ap,
        // Keys (keep as-is from server — *** means saved)
        binance_api_key:         s.binance_api_key,
        binance_api_secret:      s.binance_api_secret,
        newsapi_key:             s.newsapi_key,
        anthropic_api_key:       s.anthropic_api_key,
      }))
    } catch(e) { console.error('Failed to load settings', e) }
  }

  useEffect(() => { loadSettings() }, [])

  const set    = (k, v) => setF(p => ({...p,[k]:v}))
  const toggle = (k)    => setF(p => ({...p,[k]:p[k]==='true'?'false':'true'}))
  const isSet  = (k)    => f[k] === '***' || config[k] === '***'

  const handleSave = async () => {
    await onSave(f)
    setSaved(true)
    setTimeout(async () => {
      await loadSettings()  // Reload from DB to confirm saved state
      setSaved(false)
      onClose()
    }, 800)
  }

  const handleChangePass = async () => {
    setPassError('')
    if (newPass.length < 4) { setPassError('Minimum 4 characters'); return }
    try {
      await axios.post('/api/auth/change_password', { new_password: newPass }, { withCredentials:true })
      setPassSaved(true); setNewPass('')
      setTimeout(() => setPassSaved(false), 2000)
    } catch(e) { setPassError('Failed to change password') }
  }

  const tabs = [
    { id:'strategy', label:'Strategy' },
    { id:'risk',     label:'Risk' },
    { id:'profit',   label:'Profit' },
    { id:'pairs',    label:'Pairs' },
    { id:'keys',     label:'API Keys' },
    { id:'account',  label:'Account' },
  ]

  return (
    <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,.78)',display:'flex',alignItems:'center',justifyContent:'center',zIndex:1000}}
      onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div style={{background:'var(--bg-card)',border:'1px solid var(--border)',borderRadius:'var(--radius-lg)',width:500,maxWidth:'96vw',maxHeight:'92vh',display:'flex',flexDirection:'column'}}>

        {/* Header */}
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'16px 20px',borderBottom:'1px solid var(--border)',flexShrink:0}}>
          <span style={{fontSize:15,fontWeight:600}}>Bot Settings</span>
          <button onClick={onClose} style={{fontSize:20,color:'var(--text-2)'}}>×</button>
        </div>

        {/* Tabs */}
        <div style={{display:'flex',borderBottom:'1px solid var(--border)',flexShrink:0,overflowX:'auto'}}>
          {tabs.map(t=>(
            <button key={t.id} onClick={()=>setTab(t.id)} style={{
              padding:'10px 16px',fontSize:12,fontWeight:tab===t.id?600:400,
              borderBottom:tab===t.id?'2px solid var(--teal)':'2px solid transparent',
              color:tab===t.id?'var(--teal)':'var(--text-2)',whiteSpace:'nowrap',
            }}>{t.label}</button>
          ))}
        </div>

        {/* Content */}
        <div style={{flex:1,overflowY:'auto',padding:'20px'}}>

          {/* STRATEGY TAB */}
          {tab==='strategy'&&<>
            <InfoBox>
              Choose how the bot decides when to open trades. <b>Combined</b> runs both strategies simultaneously and trades when either fires — recommended for most users.
            </InfoBox>

            <Field label="Trading strategy" hint="">
              <div style={{display:'flex',flexDirection:'column',gap:8,marginTop:4}}>
                {[
                  ['combined',   '🔀 Combined (recommended)',  'Runs Donchian + RSI/MACD together. Trades when either strategy fires. Best overall performance.'],
                  ['donchian',   '📊 Donchian Breakout only',  'Trades when price breaks out of its recent high/low range. Lower win rate (~35%) but winning trades are significantly larger than losing ones. Based on the 43.8% APR strategy from the article.'],
                  ['confluence', '📈 RSI/MACD/BB only',        'Multi-indicator confluence. Higher win rate (~60%) but smaller average gains. More trades, tighter signals.'],
                ].map(([val,label,desc])=>(
                  <div key={val} onClick={()=>set('strategy_mode',val)} style={{
                    padding:'10px 12px',border:`1px solid ${f.strategy_mode===val?'var(--teal)':'var(--border)'}`,
                    borderRadius:6,cursor:'pointer',background:f.strategy_mode===val?'rgba(20,184,166,.08)':'transparent',
                  }}>
                    <div style={{fontWeight:600,fontSize:13,marginBottom:3,color:f.strategy_mode===val?'var(--teal)':'var(--text)'}}>{label}</div>
                    <div style={{fontSize:11,color:'var(--text-3)',lineHeight:1.5}}>{desc}</div>
                  </div>
                ))}
              </div>
            </Field>

            <Divider/>
            <SectionHead label="AI / LLM settings"/>
            <Toggle label="Use Claude AI to filter trades (requires Anthropic key)" value={f.use_llm_filter==='true'} onClick={()=>toggle('use_llm_filter')}/>
            {f.use_llm_filter==='true'&&<div style={{fontSize:11,color:'var(--text-3)',marginTop:4,marginBottom:8,lineHeight:1.5}}>
              Before each trade, Claude AI evaluates the signal against recent news and market context. Requires Anthropic API key in API Keys tab. Without the key this setting is ignored.
            </div>}
            <Toggle label="Multi-timeframe confirmation (4h confirms 1h signal)" value={f.mtf_enabled==='true'} onClick={()=>toggle('mtf_enabled')}/>
            {f.mtf_enabled==='true'&&<div style={{fontSize:11,color:'var(--text-3)',marginTop:4,marginBottom:8,lineHeight:1.5}}>
              In Combined/MTF mode, 4h candles are fetched alongside 1h. Improves signal quality but uses more API calls.
            </div>}
            <Divider/>
            <SectionHead label="Agno-style loss protection"/>
            <InfoBox>
              Inspired by the article: after N consecutive losing trades on the same pair, the bot pauses trading that pair for a cooldown period. Prevents chasing losses.
            </InfoBox>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
              <Field label="Max consecutive losses" hint="Then pause pair">
                <input type="number" step="1" min="1" max="10" value={f.max_loss_streak} onChange={e=>set('max_loss_streak',e.target.value)}/>
                <div style={{fontSize:11,color:'var(--text-3)',marginTop:4}}>e.g. 3 = after 3 losses in a row on BTC/USDT, pause BTC/USDT trading</div>
              </Field>
              <Field label="Cooldown duration (minutes)" hint="Pause length">
                <input type="number" step="15" min="15" value={f.cooldown_minutes} onChange={e=>set('cooldown_minutes',e.target.value)}/>
                <div style={{fontSize:11,color:'var(--text-3)',marginTop:4}}>e.g. 60 = pause for 1 hour before trying again</div>
              </Field>
            </div>
          </>}

          {/* RISK TAB */}
          {tab==='risk'&&<>
            <InfoBox>
              These settings control how much you risk per trade and how many trades run at once.
              <b> For Donchian strategy</b>, stop-loss and take-profit are calculated automatically from ATR (market volatility) — these % values are only used as fallback for RSI/MACD signals.
            </InfoBox>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
              <Field label="Stop-loss (%)" hint="Max loss per trade">
                <input type="number" step="0.1" value={f.stop_loss_pct} onChange={e=>set('stop_loss_pct',e.target.value)}/>
                <Hint>If price moves {f.stop_loss_pct}% against you, the trade closes. e.g. buy BTC at $100, SL at ${(100*(1-f.stop_loss_pct/100)).toFixed(2)}</Hint>
              </Field>
              <Field label="Take-profit (%)" hint="Profit target">
                <input type="number" step="0.1" value={f.take_profit_pct} onChange={e=>set('take_profit_pct',e.target.value)}/>
                <Hint>If price moves {f.take_profit_pct}% in your favour, the trade closes. e.g. buy at $100, TP at ${(100*(1+f.take_profit_pct/100)).toFixed(2)}</Hint>
              </Field>
              <Field label="Position size (USDT)" hint="Per trade">
                <input type="number" step="10" value={f.position_size_usdt} onChange={e=>set('position_size_usdt',e.target.value)}/>
                <Hint>Each trade uses ${f.position_size_usdt} USDT. With max {f.max_positions} positions that's ${(f.position_size_usdt*f.max_positions)} max deployed.</Hint>
              </Field>
              <Field label="Max open positions" hint="At the same time">
                <input type="number" step="1" min="1" max="20" value={f.max_positions} onChange={e=>set('max_positions',e.target.value)}/>
                <Hint>Bot will not open more than {f.max_positions} trades simultaneously across all pairs.</Hint>
              </Field>
              <Field label="Demo balance (USDT)" hint="Paper trading only">
                <input type="number" step="100" value={f.starting_balance} onChange={e=>set('starting_balance',e.target.value)}/>
                <Hint>Starting virtual balance for demo mode. Has no effect in live mode.</Hint>
              </Field>
            </div>
          </>}

          {/* PROFIT TAB */}
          {tab==='profit'&&<>
            <InfoBox>
              These features automatically protect and lock in profits on open trades without waiting for the full take-profit target.
            </InfoBox>

            <SectionHead label="Partial close — take early profits"/>
            <Toggle
              label="Enable partial close"
              value={f.partial_close_enabled==='true'}
              onClick={()=>toggle('partial_close_enabled')}
            />
            {f.partial_close_enabled==='true'&&<>
              <InfoBox style={{marginTop:8}}>
                Example with current settings: You buy BTC at $100. When price reaches ${(100*(1+parseFloat(f.partial_close_at_pct||1.5)/100)).toFixed(2)} (+{f.partial_close_at_pct}%), the bot sells {f.partial_close_size_pct}% of your position to lock in profit. The remaining {100-parseFloat(f.partial_close_size_pct||50)}% stays open with a trailing stop to capture more upside.
              </InfoBox>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12,marginTop:12}}>
                <Field label="Take profits when up (%)">
                  <input type="number" step="0.1" min="0.5" value={f.partial_close_at_pct} onChange={e=>set('partial_close_at_pct',e.target.value)}/>
                  <Hint>Trigger partial close when unrealized profit reaches this percentage</Hint>
                </Field>
                <Field label="Close this portion (%)">
                  <input type="number" step="10" min="10" max="90" value={f.partial_close_size_pct} onChange={e=>set('partial_close_size_pct',e.target.value)}/>
                  <Hint>Sell this % of your position. Remainder continues running.</Hint>
                </Field>
              </div>
            </>}

            <Divider/>
            <SectionHead label="Trailing stop — follow the price up"/>
            <Toggle
              label="Enable trailing stop"
              value={f.trailing_stop_enabled==='true'}
              onClick={()=>toggle('trailing_stop_enabled')}
            />
            {f.trailing_stop_enabled==='true'&&<>
              <InfoBox style={{marginTop:8}}>
                Example: You buy BTC at $100. Price rises to $102. The trailing stop moves up to ${(102*(1-parseFloat(f.trailing_stop_pct||0.8)/100)).toFixed(2)} (${(102*(1-parseFloat(f.trailing_stop_pct||0.8)/100)).toFixed(2)} = $102 − {f.trailing_stop_pct}%). If price then drops, the trade closes at that level locking in profit. The stop only moves UP, never down.
              </InfoBox>
              <div style={{marginTop:12}}>
                <Field label="Trail distance (%)">
                  <input type="number" step="0.1" min="0.1" value={f.trailing_stop_pct} onChange={e=>set('trailing_stop_pct',e.target.value)}/>
                  <Hint>Stop loss follows the price, staying {f.trailing_stop_pct}% below the highest reached price.</Hint>
                </Field>
              </div>
            </>}
          </>}

          {/* PAIRS TAB */}
          {tab==='pairs'&&<>
            <InfoBox>
              Which trading pairs the bot monitors and trades. Add any Binance spot pair ending in USDT. More pairs = more opportunities but also more concurrent positions possible.
            </InfoBox>
            <SectionHead label="Smart scanner"/>
            <Toggle label="Enable automatic pair scanning (runs every 6 hours)" value={f.scanner_enabled==='true'} onClick={()=>toggle('scanner_enabled')}/>
            {f.scanner_enabled==='true'&&<>
              <Toggle label="Auto-update active pairs after each scan" value={f.scanner_auto_update==='true'} onClick={()=>toggle('scanner_auto_update')}/>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12,marginTop:10}}>
                <Field label="Top N pairs to select" hint="from scan results">
                  <input type="number" step="1" min="3" max="15" value={f.scanner_top_n} onChange={e=>set('scanner_top_n',e.target.value)}/>
                </Field>
                <Field label="Pinned pairs (always included)" hint="Never removed by scanner">
                  <input type="text" placeholder="BTC/USDT,ETH/USDT" value={f.pinned_pairs} onChange={e=>set('pinned_pairs',e.target.value)}/>
                </Field>
              </div>
              <div style={{fontSize:11,color:'var(--text-3)',marginTop:4,lineHeight:1.5,marginBottom:12}}>
                Scanner scans all Binance USDT pairs and picks the best ones based on volume, volatility, and ADX trend strength. With Anthropic key, Claude AI ranks and explains the selection.
              </div>
            </>}
            <Divider/>
            <Field label="Active trading pairs" hint="Current list — updated by scanner or manually">
              <textarea rows={6} value={f.active_pairs} onChange={e=>set('active_pairs',e.target.value)}
                style={{resize:'vertical',fontFamily:'monospace',fontSize:12}}/>
              <Hint>
                Comma-separated USDT pairs. Recommended quality pairs: BTC/USDT, ETH/USDT, SOL/USDT, BNB/USDT, LINK/USDT, AVAX/USDT, DOT/USDT, MATIC/USDT<br/>
                Crypto/BTC pairs also work (e.g. ETH/BTC). Commodities on Binance: XAUUSDT (Gold), XAGUSDT (Silver) — add without slash as XAU/USDT.<br/>
                Avoid micro-cap alts like HIGH, SAPIEN, AUDIO — low liquidity causes wide spreads.
              </Hint>
            </Field>
          </>}

          
          {/* API KEYS TAB */}
          {tab==='keys'&&(
            <div>
              <InfoBox>
                API keys are stored securely in the database and survive all future updates. They are never exposed in logs.
                <br/><br/>
                <b>Binance keys:</b> Required only for live trading. Not needed for demo mode.<br/>
                <b>NewsAPI key:</b> Free at newsapi.org — enables better news coverage.<br/>
                <b>Anthropic key:</b> Enables Claude AI trade filtering and smart news analysis.
              </InfoBox>
              <div style={{display:'flex',justifyContent:'flex-end',marginBottom:12}}>
                <button onClick={()=>setShowSecrets(s=>!s)} style={{fontSize:11,color:'var(--text-2)',border:'1px solid var(--border)',borderRadius:4,padding:'4px 10px'}}>
                  {showSecrets?'🙈 Hide keys':'👁 Show keys'}
                </button>
              </div>
              {[
                ['Binance API Key',    'binance_api_key',    'Enable in Binance → API Management → Spot Trading only'],
                ['Binance API Secret', 'binance_api_secret', 'Never share this with anyone'],
                ['NewsAPI Key',        'newsapi_key',        'Free tier: 100 requests/day at newsapi.org'],
                ['Anthropic API Key',  'anthropic_api_key',  'console.anthropic.com — enables Claude AI filtering'],
              ].map(([label,key,hint])=>{
                const saved = f[key] === '***'
                const hasNew = f[key] && f[key] !== '***'
                return (
                  <Field key={key} label={label}
                    hint={saved ? '✓ Saved' : hasNew ? 'Ready to save' : '⚠ Not set'}
                    hintOk={saved || hasNew}>
                    {saved && !showSecrets ? (
                      <div style={{display:'flex',gap:8,alignItems:'center'}}>
                        <div style={{flex:1,padding:'6px 10px',background:'var(--bg-surface)',border:'1px solid var(--green-dim)',borderRadius:'var(--radius)',fontSize:12,color:'var(--green)',letterSpacing:2}}>
                          ••••••••••••••••••••••••
                        </div>
                        <button onClick={()=>set(key,'')} style={{padding:'6px 10px',border:'1px solid var(--border)',borderRadius:'var(--radius)',fontSize:11,color:'var(--text-2)',whiteSpace:'nowrap'}}>
                          Replace
                        </button>
                      </div>
                    ) : (
                      <input type={showSecrets ? 'text' : 'password'}
                        placeholder="Paste key here"
                        value={saved ? '' : (f[key] || '')}
                        onChange={e=>set(key, e.target.value)}
                        autoComplete="off"
                      />
                    )}
                    <Hint>{hint}</Hint>
                  </Field>
                )
              })}
              <Divider/>
              <div style={{display:'flex',alignItems:'center',gap:10}}>
                <button onClick={async()=>{
                  setAiTest('Testing...')
                  try {
                    const r = await fetch('/api/ai/test', {credentials:'include'})
                    const d = await r.json()
                    setAiTest(d.ok ? '✓ '+d.message : '✗ '+d.error)
                  } catch(e) { setAiTest('✗ Request failed') }
                }} style={{padding:'7px 16px',borderRadius:6,background:'rgba(168,85,247,.15)',border:'1px solid rgba(168,85,247,.3)',color:'#a855f7',fontWeight:600,fontSize:12}}>
                  🤖 Test AI connection
                </button>
                {aiTest&&<span style={{fontSize:12,color:aiTest.startsWith('✓')?'var(--green)':'var(--red)'}}>{aiTest}</span>}
              </div>
            </div>
          )}

          {/* ACCOUNT TAB */}
          {tab==='account'&&<>
            <InfoBox>Logged in as <b>{username}</b></InfoBox>
            <Divider/>
            <SectionHead label="Change password"/>
            <Field label="New password">
              <input type="password" value={newPass} onChange={e=>setNewPass(e.target.value)} placeholder="Enter new password (min 4 chars)"/>
            </Field>
            {passError&&<div style={{fontSize:12,color:'var(--red)',marginBottom:8}}>{passError}</div>}
            <button onClick={handleChangePass} style={{padding:'7px 20px',borderRadius:6,background:passSaved?'var(--green)':'var(--blue-bg)',border:'1px solid var(--blue)',color:passSaved?'#fff':'var(--blue)',fontWeight:600,fontSize:12}}>
              {passSaved?'Password changed ✓':'Change password'}
            </button>
            <Divider/>
            <SectionHead label="Demo trading"/>
            <div style={{fontSize:12,color:'var(--text-2)',marginBottom:10,lineHeight:1.6}}>
              Clear all paper trades and reset the demo balance back to the starting amount.
              Useful when you want a fresh start after testing or changing strategy.
              This only affects demo trades — live trades are never deleted.
            </div>
            {resetError&&<div style={{fontSize:12,color:'var(--red)',marginBottom:8}}>{resetError}</div>}
            <button onClick={async()=>{
              if(!window.confirm('Clear ALL demo trades and reset balance?\n\nThis cannot be undone.')) return
              setResetError('')
              try {
                const r = await fetch('/api/demo/reset',{method:'POST',credentials:'include'})
                const d = await r.json()
                if(d.ok){ setResetDone(true); setTimeout(()=>setResetDone(false),3000) }
                else setResetError(d.error||'Reset failed')
              } catch(e){ setResetError('Request failed') }
            }} style={{
              padding:'7px 20px',borderRadius:6,fontWeight:600,fontSize:12,
              background:resetDone?'var(--green-bg)':'var(--amber-bg)',
              border:`1px solid ${resetDone?'var(--green-dim)':'var(--amber)'}`,
              color:resetDone?'var(--green)':'var(--amber)',marginBottom:16,
            }}>
              {resetDone?'✓ Demo reset successfully':'🗑 Reset demo trades & balance'}
            </button>
            <Divider/>
            <button onClick={onLogout} style={{padding:'7px 20px',borderRadius:6,background:'var(--red-bg)',border:'1px solid var(--red-dim)',color:'var(--red)',fontWeight:600,fontSize:12}}>
              Sign out
            </button>
          </>}
        </div>

        {/* Footer */}
        {tab!=='account'&&(
          <div style={{display:'flex',gap:8,justifyContent:'flex-end',padding:'14px 20px',borderTop:'1px solid var(--border)',flexShrink:0}}>
            <button onClick={onClose} style={{padding:'7px 16px',borderRadius:6,border:'1px solid var(--border)',color:'var(--text-2)'}}>Cancel</button>
            <button onClick={handleSave} style={{padding:'7px 24px',borderRadius:6,background:saved?'var(--green)':'var(--teal)',color:'#fff',fontWeight:600,transition:'background .2s'}}>
              {saved?'Saved ✓':'Save settings'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function SectionHead({label}){
  return <div style={{fontSize:11,fontWeight:600,textTransform:'uppercase',letterSpacing:.5,color:'var(--text-3)',marginBottom:10}}>{label}</div>
}
function Divider(){ return <div style={{height:1,background:'var(--border)',margin:'16px 0'}}/> }
function InfoBox({children,style}){
  return <div style={{background:'var(--blue-bg)',border:'1px solid rgba(59,130,246,.2)',borderRadius:6,padding:'10px 12px',fontSize:12,color:'var(--text-2)',lineHeight:1.6,marginBottom:14,...style}}>{children}</div>
}
function Hint({children}){
  return <div style={{fontSize:11,color:'var(--text-3)',marginTop:4,lineHeight:1.5}}>{children}</div>
}
function Field({label,hint,hintOk,children}){
  return <div style={{marginBottom:14}}>
    {(label||hint)&&<div style={{display:'flex',justifyContent:'space-between',marginBottom:5}}>
      {label&&<label style={{fontSize:12,fontWeight:500}}>{label}</label>}
      {hint&&<span style={{fontSize:11,color:hintOk?'var(--green)':'var(--text-3)'}}>{hint}</span>}
    </div>}
    {children}
  </div>
}
function Toggle({label,value,onClick}){
  return <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',padding:'4px 0'}}>
    <span style={{fontSize:13}}>{label}</span>
    <div onClick={onClick} style={{width:40,height:22,borderRadius:11,background:value?'var(--teal)':'var(--border)',cursor:'pointer',position:'relative',transition:'background .2s',flexShrink:0}}>
      <div style={{position:'absolute',top:3,left:value?20:3,width:16,height:16,borderRadius:'50%',background:'#fff',transition:'left .2s'}}/>
    </div>
  </div>
}
