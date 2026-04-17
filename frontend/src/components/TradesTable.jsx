import React from 'react'

function formatPrice(p) {
  if (!p) return '—'
  if (p > 1000) return p.toLocaleString('en-US', { maximumFractionDigits: 2 })
  if (p > 1)    return p.toFixed(4)
  return p.toFixed(6)
}

function formatTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return `${d.getUTCHours().toString().padStart(2,'0')}:${d.getUTCMinutes().toString().padStart(2,'0')}`
}

export default function TradesTable({ trades = [], mode }) {
  return (
    <div style={{
      margin: '8px 12px', flexShrink: 0,
      background: 'var(--bg-card)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius)', overflow: 'hidden',
    }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '8px 12px', borderBottom: '1px solid var(--border)',
      }}>
        <span style={{ fontWeight: 600, fontSize: 12 }}>Recent trades</span>
        {mode === 'demo' && (
          <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 10, background: 'var(--blue-bg)', color: 'var(--blue)' }}>
            Paper trades
          </span>
        )}
      </div>

      <div style={{ overflowX: 'auto', maxHeight: 155, overflowY: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              {['Time','Pair','Side','Entry','Exit','P&L','Status','Reason'].map(h => (
                <th key={h} style={{
                  padding: '5px 10px', textAlign: 'left', fontSize: 10,
                  color: 'var(--text-3)', fontWeight: 500, whiteSpace: 'nowrap',
                  position: 'sticky', top: 0, background: 'var(--bg-card)',
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {trades.length === 0 ? (
              <tr><td colSpan={8} style={{ padding: '16px 10px', color: 'var(--text-3)', textAlign: 'center' }}>
                No trades yet — start the bot to begin
              </td></tr>
            ) : trades.map(t => {
              const pnl = t.pnl ?? t.unrealized_pnl
              const isOpen = t.status === 'open'
              return (
                <tr key={t.id}
                  style={{ borderBottom: '1px solid var(--border-dim)' }}
                  onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                  <td style={{ padding: '5px 10px', color: 'var(--text-2)', whiteSpace: 'nowrap' }}>{formatTime(t.opened_at)}</td>
                  <td style={{ padding: '5px 10px', fontWeight: 600 }}>{t.pair}</td>
                  <td style={{ padding: '5px 10px' }}>
                    <span className={`badge badge-${(t.side||'').toLowerCase()}`}>{t.side}</span>
                  </td>
                  <td style={{ padding: '5px 10px', fontFamily: 'monospace' }}>{formatPrice(t.entry_price)}</td>
                  <td style={{ padding: '5px 10px', fontFamily: 'monospace', color: 'var(--text-2)' }}>
                    {t.exit_price ? formatPrice(t.exit_price) : '—'}
                  </td>
                  <td style={{ padding: '5px 10px', fontWeight: 600,
                    color: pnl == null ? 'var(--text-2)' : pnl >= 0 ? 'var(--green)' : 'var(--red)' }}>
                    {pnl == null ? '—' : `${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}`}
                    {isOpen && pnl != null && <span style={{ fontSize: 9, marginLeft: 3, color: 'var(--text-3)' }}>unrlz</span>}
                  </td>
                  <td style={{ padding: '5px 10px' }}>
                    <span style={{
                      fontSize: 10, padding: '1px 6px', borderRadius: 10, fontWeight: 500,
                      background: isOpen ? 'var(--amber-bg)' : 'var(--bg-hover)',
                      color:      isOpen ? 'var(--amber)'   : 'var(--text-2)',
                    }}>{isOpen ? 'Open' : 'Closed'}</span>
                  </td>
                  <td style={{ padding: '5px 10px', color: 'var(--text-2)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {t.strategy_reason || '—'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
