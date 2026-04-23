import React from 'react'
import axios from 'axios'

export default function Topbar({ data, connected, onStart, onStop, onModeChange }) {
  const running   = data?.bot_running
  const mode      = data?.mode || 'demo'
  const stats     = data?.stats || {}
  const llmToday  = data?.llm_today || 0
  const llmCost   = data?.llm_cost_today || 0

  return (
    <div style={{
      height: 48, flexShrink: 0,
      background: 'var(--bg-surface)',
      borderBottom: '1px solid var(--border)',
      display: 'flex', alignItems: 'center',
      padding: '0 12px', gap: 10, zIndex: 100,
    }}>
      {/* Brand */}
      <div style={{ display:'flex', alignItems:'center', gap:8, flexShrink:0 }}>
        <span style={{ fontSize:20 }}>⚡</span>
        <span style={{ fontWeight:700, fontSize:14 }}>Trading Bot</span>
      </div>

      {/* DEMO / LIVE */}
      <div style={{ display:'flex', gap:2, background:'var(--bg-card)',
        borderRadius:6, padding:2, flexShrink:0 }}>
        {['demo','live'].map(m => (
          <button key={m} onClick={()=>onModeChange(m)} style={{
            padding:'3px 10px', borderRadius:4, fontSize:11, fontWeight:600,
            background: mode===m ? (m==='live'?'var(--red)':'var(--blue)') : 'transparent',
            color: mode===m ? '#fff' : 'var(--text-3)',
            border:'none', cursor:'pointer', textTransform:'uppercase',
          }}>{m}</button>
        ))}
      </div>

      {/* Smart mode only — scalp removed based on performance data */}

      {/* LLM cost */}
        <div style={{ fontSize:11, color:'var(--text-3)',
          background:'var(--bg-card)', padding:'3px 8px',
          borderRadius:6, flexShrink:0, display:'flex', gap:4 }}>
          <span>🤖</span>
          <span>{llmToday} calls today</span>
          <span style={{color:'var(--text-2)'}}>≈${llmCost.toFixed(4)}</span>
        </div>

      {/* Connection status */}
      <div style={{ display:'flex', alignItems:'center', gap:4, flexShrink:0 }}>
        <div style={{ width:6, height:6, borderRadius:'50%',
          background: connected ? 'var(--green)' : 'var(--red)' }}/>
        <span style={{ fontSize:11, color:'var(--text-3)' }}>
          {connected ? 'Live' : 'Offline'}
        </span>
      </div>

      <div style={{ flex:1 }}/>

      {/* Stats */}
      <div style={{ display:'flex', gap:16, alignItems:'center' }}>
        {[
          ['Win rate', stats.win_rate != null ? `${stats.win_rate}%` : '—'],
          ['Total P&L', stats.total_pnl != null ? `${stats.total_pnl >= 0 ? '+' : ''}$${(stats.total_pnl||0).toFixed(2)}` : '—'],
          ['Trades', stats.total_trades || 0],
        ].map(([label, val]) => (
          <div key={label} style={{ textAlign:'center' }}>
            <div style={{ fontSize:9, color:'var(--text-3)', textTransform:'uppercase', letterSpacing:.5 }}>{label}</div>
            <div style={{ fontSize:13, fontWeight:700, color: label==='Total P&L' ? ((stats.total_pnl||0)>=0?'var(--green)':'var(--red)') : 'var(--text)' }}>{val}</div>
          </div>
        ))}
      </div>

      {/* Start/Stop */}
      <button onClick={running ? onStop : onStart} style={{
        padding:'6px 16px', borderRadius:6, fontWeight:600, fontSize:12,
        background: running ? 'var(--red)' : 'var(--green)',
        color:'#fff', border:'none', cursor:'pointer', flexShrink:0,
      }}>
        {running ? 'Stop bot' : 'Start bot'}
      </button>

      {/* Running indicator */}
      {running && (
        <span style={{ fontSize:11, color:'var(--green)', flexShrink:0 }}>● Running</span>
      )}
    </div>
  )
}
