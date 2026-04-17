import React, { useState, useEffect } from 'react'

export default function SettingsModal({ config = {}, onSave, onClose }) {
  const [f, setF] = useState({
    stop_loss_pct:'1.5', take_profit_pct:'3.0', position_size_usdt:'100',
    max_positions:'5', active_pairs:'BTC/USDT,ETH/USDT,BNB/USDT,SOL/USDT,XRP/USDT,ADA/USDT,DOGE/USDT,AVAX/USDT',
    starting_balance:'1000',
    trailing_stop_enabled:'true', trailing_stop_pct:'0.8',
    partial_close_enabled:'true', partial_close_at_pct:'1.5', partial_close_size_pct:'50',
    binance_api_key:'', binance_api_secret:'', newsapi_key:'',
  })
  const [showSecrets, setShowSecrets] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    const ap = Array.isArray(config.active_pairs) ? config.active_pairs.join(',') : config.active_pairs||''
    setF(prev => ({...prev,...config,active_pairs:ap,
      binance_api_key:    config.binance_api_key    ==='***'?'':(config.binance_api_key||''),
      binance_api_secret: config.binance_api_secret ==='***'?'':(config.binance_api_secret||''),
      newsapi_key:        config.newsapi_key        ==='***'?'':(config.newsapi_key||''),
    }))
  }, [config])

  const set = (k, v) => setF(p => ({...p, [k]: v}))
  const toggle = (k) => setF(p => ({...p, [k]: p[k]==='true'?'false':'true'}))
  const isSet  = (k) => config[k] === '***'

  const handleSave = () => {
    onSave(f); setSaved(true)
    setTimeout(() => { setSaved(false); onClose() }, 800)
  }

  return (
    <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,.78)',display:'flex',alignItems:'center',justifyContent:'center',zIndex:1000}}
      onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div style={{background:'var(--bg-card)',border:'1px solid var(--border)',borderRadius:'var(--radius-lg)',padding:24,width:460,maxWidth:'95vw',maxHeight:'90vh',overflowY:'auto'}}>

        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:20}}>
          <span style={{fontSize:15,fontWeight:600}}>Bot Settings</span>
          <button onClick={onClose} style={{fontSize:20,color:'var(--text-2)'}}>×</button>
        </div>

        {/* API Keys */}
        <SectionHead label="API Keys" action={
          <button onClick={()=>setShowSecrets(s=>!s)} style={{fontSize:11,color:'var(--text-2)',border:'1px solid var(--border)',borderRadius:4,padding:'2px 8px'}}>
            {showSecrets?'Hide keys':'Show keys'}
          </button>}/>
        <Field label="Binance API Key"    hint={isSet('binance_api_key')    ?'✓ Saved':'Not set'} hintOk={isSet('binance_api_key')}>
          <input type={showSecrets?'text':'password'} placeholder={isSet('binance_api_key')?'Leave blank to keep current':'Enter key'} value={f.binance_api_key} onChange={e=>set('binance_api_key',e.target.value)}/>
        </Field>
        <Field label="Binance API Secret" hint={isSet('binance_api_secret') ?'✓ Saved':'Not set'} hintOk={isSet('binance_api_secret')}>
          <input type={showSecrets?'text':'password'} placeholder={isSet('binance_api_secret')?'Leave blank to keep current':'Enter secret'} value={f.binance_api_secret} onChange={e=>set('binance_api_secret',e.target.value)}/>
        </Field>
        <Field label="NewsAPI Key" hint={isSet('newsapi_key')?'✓ Saved':'Free at newsapi.org'} hintOk={isSet('newsapi_key')}>
          <input type={showSecrets?'text':'password'} placeholder={isSet('newsapi_key')?'Leave blank to keep current':'Enter key'} value={f.newsapi_key} onChange={e=>set('newsapi_key',e.target.value)}/>
        </Field>

        <Divider/>

        {/* Strategy */}
        <SectionHead label="Risk Management"/>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
          <Field label="Stop-loss (%)" hint="Max loss/trade">
            <input type="number" step="0.1" value={f.stop_loss_pct} onChange={e=>set('stop_loss_pct',e.target.value)}/>
          </Field>
          <Field label="Take-profit (%)" hint="Profit target">
            <input type="number" step="0.1" value={f.take_profit_pct} onChange={e=>set('take_profit_pct',e.target.value)}/>
          </Field>
          <Field label="Position size (USDT)" hint="Per trade">
            <input type="number" step="10" value={f.position_size_usdt} onChange={e=>set('position_size_usdt',e.target.value)}/>
          </Field>
          <Field label="Max positions" hint="Concurrent">
            <input type="number" step="1" min="1" max="20" value={f.max_positions} onChange={e=>set('max_positions',e.target.value)}/>
          </Field>
          <Field label="Demo balance (USDT)" hint="Paper trading">
            <input type="number" step="100" value={f.starting_balance} onChange={e=>set('starting_balance',e.target.value)}/>
          </Field>
        </div>

        <Divider/>

        {/* Profit management */}
        <SectionHead label="Profit Management"/>
        <Toggle label="Partial close (take partial profits early)" value={f.partial_close_enabled==='true'} onClick={()=>toggle('partial_close_enabled')}/>
        {f.partial_close_enabled==='true' && (
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12,marginTop:10}}>
            <Field label="Take profits at (%)" hint="e.g. 1.5 = +1.5%">
              <input type="number" step="0.1" value={f.partial_close_at_pct} onChange={e=>set('partial_close_at_pct',e.target.value)}/>
            </Field>
            <Field label="Close this much (%)" hint="e.g. 50 = half">
              <input type="number" step="10" value={f.partial_close_size_pct} onChange={e=>set('partial_close_size_pct',e.target.value)}/>
            </Field>
          </div>
        )}

        <div style={{marginTop:12}}>
          <Toggle label="Trailing stop (lock in profits as price moves up)" value={f.trailing_stop_enabled==='true'} onClick={()=>toggle('trailing_stop_enabled')}/>
          {f.trailing_stop_enabled==='true' && (
            <div style={{marginTop:10}}>
              <Field label="Trail distance (%)" hint="Stop follows price this close">
                <input type="number" step="0.1" value={f.trailing_stop_pct} onChange={e=>set('trailing_stop_pct',e.target.value)}/>
              </Field>
            </div>
          )}
        </div>

        <Divider/>

        {/* Pairs */}
        <SectionHead label="Active Pairs"/>
        <Field label="" hint="One per line or comma-separated">
          <textarea rows={4} value={f.active_pairs} onChange={e=>set('active_pairs',e.target.value)}
            style={{resize:'vertical',fontFamily:'monospace',fontSize:11}}/>
        </Field>

        <div style={{display:'flex',gap:8,justifyContent:'flex-end',marginTop:8}}>
          <button onClick={onClose} style={{padding:'7px 16px',borderRadius:6,border:'1px solid var(--border)',color:'var(--text-2)'}}>Cancel</button>
          <button onClick={handleSave} style={{padding:'7px 24px',borderRadius:6,background:saved?'var(--green)':'var(--teal)',color:'#fff',fontWeight:600,transition:'background .2s'}}>
            {saved?'Saved ✓':'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}

function SectionHead({label,action}){
  return <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:12}}>
    <span style={{fontSize:11,fontWeight:600,textTransform:'uppercase',letterSpacing:.5,color:'var(--text-3)'}}>{label}</span>
    {action}
  </div>
}
function Divider(){ return <div style={{height:1,background:'var(--border)',margin:'16px 0'}}/> }
function Field({label,hint,hintOk,children}){
  return <div style={{marginBottom:12}}>
    {label&&<div style={{display:'flex',justifyContent:'space-between',marginBottom:5}}>
      <label style={{fontSize:12,fontWeight:500}}>{label}</label>
      {hint&&<span style={{fontSize:11,color:hintOk?'var(--green)':'var(--text-3)'}}>{hint}</span>}
    </div>}
    {children}
  </div>
}
function Toggle({label,value,onClick}){
  return <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',padding:'8px 0'}}>
    <span style={{fontSize:12,color:'var(--text)'}}>{label}</span>
    <div onClick={onClick} style={{width:40,height:22,borderRadius:11,background:value?'var(--teal)':'var(--border)',cursor:'pointer',position:'relative',transition:'background .2s',flexShrink:0}}>
      <div style={{position:'absolute',top:3,left:value?20:3,width:16,height:16,borderRadius:'50%',background:'#fff',transition:'left .2s'}}/>
    </div>
  </div>
}
