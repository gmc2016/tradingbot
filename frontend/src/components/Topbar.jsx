import React from 'react'

export default function Topbar({ data, connected, onStart, onStop, onModeChange }) {
  const running = data?.bot_running
  const mode    = data?.mode || 'demo'
  const stats   = data?.stats || {}

  return (
    <div style={{
      height: 48, flexShrink: 0,
      background: 'var(--bg-surface)',
      borderBottom: '1px solid var(--border)',
      display: 'flex', alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 16px', gap: 12,
    }}>
      {/* Left */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span style={{ fontWeight: 700, fontSize: 15, color: 'var(--text)' }}>
          📈 Trading Bot
        </span>

        {/* Mode toggle */}
        <div style={{
          display: 'flex', overflow: 'hidden',
          border: '1px solid var(--border)', borderRadius: 6,
          background: 'var(--bg-base)',
        }}>
          {['demo', 'live'].map(m => (
            <button key={m} onClick={() => onModeChange(m)} style={{
              padding: '4px 14px', fontSize: 11, fontWeight: 600,
              textTransform: 'uppercase', letterSpacing: 0.4,
              background: mode === m
                ? (m === 'live' ? 'var(--green-bg)' : 'var(--blue-bg)')
                : 'transparent',
              color: mode === m
                ? (m === 'live' ? 'var(--green)' : 'var(--blue)')
                : 'var(--text-3)',
            }}>{m}</button>
          ))}
        </div>

        {mode === 'live' && (
          <span style={{
            fontSize: 11, fontWeight: 600, color: 'var(--red)',
            background: 'var(--red-bg)', border: '1px solid var(--red-dim)',
            borderRadius: 6, padding: '3px 10px',
          }}>⚠ LIVE — REAL FUNDS</span>
        )}
      </div>

      {/* Right */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        {/* WS dot */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <div style={{
            width: 7, height: 7, borderRadius: '50%',
            background: connected ? 'var(--green)' : 'var(--red)',
          }} />
          <span style={{ fontSize: 11, color: 'var(--text-2)' }}>
            {connected ? 'Live' : 'Offline'}
          </span>
        </div>

        {/* Stats strip */}
        <div style={{
          display: 'flex', gap: 16, padding: '4px 14px',
          background: 'var(--bg-base)', border: '1px solid var(--border)',
          borderRadius: 6,
        }}>
          <MiniStat label="Win rate"   value={`${stats.win_rate || 0}%`} />
          <MiniStat label="Total P&L"  value={`${(stats.total_pnl||0) >= 0 ? '+' : ''}$${stats.total_pnl || 0}`}
                    color={(stats.total_pnl||0) >= 0 ? 'var(--green)' : 'var(--red)'} />
          <MiniStat label="Trades"     value={stats.total_trades || 0} />
        </div>

        {/* Bot control */}
        {running ? (
          <button onClick={onStop} style={{
            padding: '6px 16px', borderRadius: 6, fontWeight: 600,
            background: 'var(--red-bg)', border: '1px solid var(--red-dim)',
            color: 'var(--red)',
          }}>Stop bot</button>
        ) : (
          <button onClick={onStart} style={{
            padding: '6px 16px', borderRadius: 6, fontWeight: 600,
            background: 'var(--green-bg)', border: '1px solid var(--green-dim)',
            color: 'var(--green)',
          }}>Start bot</button>
        )}

        {running && (
          <span style={{ fontSize: 11, color: 'var(--green)', display: 'flex', alignItems: 'center', gap: 5 }}>
            <PulseDot /> Running
          </span>
        )}
      </div>
    </div>
  )
}

function MiniStat({ label, value, color }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: 10, color: 'var(--text-3)', marginBottom: 1 }}>{label}</div>
      <div style={{ fontSize: 12, fontWeight: 600, color: color || 'var(--text)' }}>{value}</div>
    </div>
  )
}

function PulseDot() {
  return (
    <>
      <style>{`@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(1.5)}}`}</style>
      <div style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--green)', animation: 'pulse 1.5s infinite' }} />
    </>
  )
}
