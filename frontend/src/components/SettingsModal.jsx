import React, { useState, useEffect } from 'react'

export default function SettingsModal({ config = {}, onSave, onClose }) {
  const [f, setF] = useState({
    stop_loss_pct: '1.5', take_profit_pct: '3.0',
    position_size_usdt: '100', max_positions: '3',
    active_pairs: 'BTC/USDT,ETH/USDT,BNB/USDT,SOL/USDT,XRP/USDT',
    starting_balance: '1000',
    binance_api_key: '', binance_api_secret: '', newsapi_key: '',
  })
  const [showSecrets, setShowSecrets] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    const ap = Array.isArray(config.active_pairs)
      ? config.active_pairs.join(',')
      : config.active_pairs || ''
    setF(prev => ({
      ...prev, ...config, active_pairs: ap,
      // Don't prefill masked values
      binance_api_key:    config.binance_api_key    === '***' ? '' : (config.binance_api_key    || ''),
      binance_api_secret: config.binance_api_secret === '***' ? '' : (config.binance_api_secret || ''),
      newsapi_key:        config.newsapi_key        === '***' ? '' : (config.newsapi_key        || ''),
    }))
  }, [config])

  const set = (k, v) => setF(p => ({ ...p, [k]: v }))

  const handleSave = () => {
    onSave(f)
    setSaved(true)
    setTimeout(() => { setSaved(false); onClose() }, 800)
  }

  const isKeySet = (k) => config[k] === '***'

  return (
    <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,.75)', display:'flex', alignItems:'center', justifyContent:'center', zIndex:1000 }}
      onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={{ background:'var(--bg-card)', border:'1px solid var(--border)', borderRadius:'var(--radius-lg)', padding:24, width:440, maxWidth:'94vw', maxHeight:'90vh', overflowY:'auto' }}>

        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:20 }}>
          <span style={{ fontSize:15, fontWeight:600 }}>Bot Settings</span>
          <button onClick={onClose} style={{ fontSize:20, color:'var(--text-2)', lineHeight:1 }}>×</button>
        </div>

        {/* API Keys section */}
        <SectionLabel label="API Keys" extra={
          <button onClick={() => setShowSecrets(s => !s)} style={{ fontSize:11, color:'var(--text-2)', border:'1px solid var(--border)', borderRadius:4, padding:'2px 8px' }}>
            {showSecrets ? 'Hide' : 'Show'}
          </button>
        }/>

        <Field label="Binance API Key" hint={isKeySet('binance_api_key') ? '✓ Saved' : 'Not set'} hintColor={isKeySet('binance_api_key') ? 'var(--green)' : 'var(--amber)'}>
          <input
            type={showSecrets ? 'text' : 'password'}
            placeholder={isKeySet('binance_api_key') ? 'Leave blank to keep current' : 'Enter API key'}
            value={f.binance_api_key}
            onChange={e => set('binance_api_key', e.target.value)}
          />
        </Field>

        <Field label="Binance API Secret" hint={isKeySet('binance_api_secret') ? '✓ Saved' : 'Not set'} hintColor={isKeySet('binance_api_secret') ? 'var(--green)' : 'var(--amber)'}>
          <input
            type={showSecrets ? 'text' : 'password'}
            placeholder={isKeySet('binance_api_secret') ? 'Leave blank to keep current' : 'Enter API secret'}
            value={f.binance_api_secret}
            onChange={e => set('binance_api_secret', e.target.value)}
          />
        </Field>

        <Field label="NewsAPI Key" hint={isKeySet('newsapi_key') ? '✓ Saved' : 'Not set'} hintColor={isKeySet('newsapi_key') ? 'var(--green)' : 'var(--amber)'}>
          <input
            type={showSecrets ? 'text' : 'password'}
            placeholder={isKeySet('newsapi_key') ? 'Leave blank to keep current' : 'Get free key at newsapi.org'}
            value={f.newsapi_key}
            onChange={e => set('newsapi_key', e.target.value)}
          />
        </Field>

        <div style={{ height:1, background:'var(--border)', margin:'16px 0' }}/>

        {/* Strategy section */}
        <SectionLabel label="Strategy" />

        {[
          ['Stop-loss (%)',         'stop_loss_pct',       '0.1', 'Max loss per trade'],
          ['Take-profit (%)',       'take_profit_pct',     '0.1', 'Profit target per trade'],
          ['Position size (USDT)', 'position_size_usdt',  '10',  'USDT per trade'],
          ['Max open positions',   'max_positions',       '1',   '1–5 recommended'],
          ['Demo balance (USDT)',  'starting_balance',    '100', 'Paper trading balance'],
        ].map(([label, key, step, hint]) => (
          <Field key={key} label={label} hint={hint}>
            <input type="number" step={step} value={f[key]} onChange={e => set(key, e.target.value)} />
          </Field>
        ))}

        <Field label="Active pairs" hint="Comma-separated">
          <textarea rows={3} value={f.active_pairs} onChange={e => set('active_pairs', e.target.value)}
            style={{ resize:'vertical', fontFamily:'monospace', fontSize:11 }} />
        </Field>

        <div style={{ display:'flex', gap:8, justifyContent:'flex-end', marginTop:8 }}>
          <button onClick={onClose} style={{ padding:'7px 16px', borderRadius:6, border:'1px solid var(--border)', color:'var(--text-2)' }}>
            Cancel
          </button>
          <button onClick={handleSave} style={{ padding:'7px 24px', borderRadius:6, background: saved ? 'var(--green)' : 'var(--teal)', color:'#fff', fontWeight:600, transition:'background .2s' }}>
            {saved ? 'Saved ✓' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}

function SectionLabel({ label, extra }) {
  return (
    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:12 }}>
      <span style={{ fontSize:11, fontWeight:600, textTransform:'uppercase', letterSpacing:.5, color:'var(--text-3)' }}>{label}</span>
      {extra}
    </div>
  )
}

function Field({ label, hint, hintColor, children }) {
  return (
    <div style={{ marginBottom:14 }}>
      <div style={{ display:'flex', justifyContent:'space-between', marginBottom:5 }}>
        <label style={{ fontSize:12, fontWeight:500 }}>{label}</label>
        {hint && <span style={{ fontSize:11, color: hintColor || 'var(--text-3)' }}>{hint}</span>}
      </div>
      {children}
    </div>
  )
}
