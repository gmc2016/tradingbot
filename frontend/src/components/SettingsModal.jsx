import React, { useState, useEffect } from 'react'

export default function SettingsModal({ config = {}, onSave, onClose }) {
  const [f, setF] = useState({
    stop_loss_pct: '1.5', take_profit_pct: '3.0',
    position_size_usdt: '100', max_positions: '3',
    active_pairs: 'BTC/USDT,ETH/USDT,BNB/USDT,SOL/USDT,XRP/USDT',
    starting_balance: '1000',
  })

  useEffect(() => {
    const ap = Array.isArray(config.active_pairs)
      ? config.active_pairs.join(',')
      : config.active_pairs || ''
    setF(prev => ({ ...prev, ...config, active_pairs: ap }))
  }, [config])

  const set = (k, v) => setF(p => ({ ...p, [k]: v }))

  const fields = [
    ['Stop-loss (%)',         'stop_loss_pct',       '0.1', 'Per-trade maximum loss'],
    ['Take-profit (%)',       'take_profit_pct',     '0.1', 'Per-trade profit target'],
    ['Position size (USDT)', 'position_size_usdt',  '10',  'USDT per trade'],
    ['Max open positions',   'max_positions',       '1',   '1–5 recommended'],
    ['Demo balance (USDT)',  'starting_balance',    '100', 'Reset on save'],
  ]

  return (
    <div
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div style={{
        background: 'var(--bg-card)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)', padding: 24, width: 420, maxWidth: '92vw',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <span style={{ fontSize: 15, fontWeight: 600 }}>Bot Settings</span>
          <button onClick={onClose} style={{ fontSize: 20, color: 'var(--text-2)', lineHeight: 1 }}>×</button>
        </div>

        {fields.map(([label, key, step, hint]) => (
          <div key={key} style={{ marginBottom: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
              <label style={{ fontSize: 12, fontWeight: 500 }}>{label}</label>
              <span style={{ fontSize: 11, color: 'var(--text-3)' }}>{hint}</span>
            </div>
            <input type="number" step={step} value={f[key]} onChange={e => set(key, e.target.value)} />
          </div>
        ))}

        <div style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
            <label style={{ fontSize: 12, fontWeight: 500 }}>Active pairs</label>
            <span style={{ fontSize: 11, color: 'var(--text-3)' }}>Comma-separated</span>
          </div>
          <textarea rows={3} value={f.active_pairs} onChange={e => set('active_pairs', e.target.value)}
            style={{ resize: 'vertical', fontFamily: 'monospace', fontSize: 11 }} />
        </div>

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button onClick={onClose} style={{
            padding: '7px 16px', borderRadius: 6,
            border: '1px solid var(--border)', color: 'var(--text-2)',
          }}>Cancel</button>
          <button onClick={() => { onSave(f); onClose() }} style={{
            padding: '7px 20px', borderRadius: 6,
            background: 'var(--teal)', color: '#fff', fontWeight: 600,
          }}>Save</button>
        </div>
      </div>
    </div>
  )
}
