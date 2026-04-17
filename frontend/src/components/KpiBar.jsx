import React from 'react'

export default function KpiBar({ stats = {}, openTrades = [], maxPositions = 3 }) {
  const cards = [
    {
      label: 'Total P&L',
      value: `${(stats.total_pnl || 0) >= 0 ? '+' : ''}$${(stats.total_pnl || 0).toFixed(2)}`,
      sub:   `${stats.total_trades || 0} total trades`,
      color: (stats.total_pnl || 0) >= 0 ? 'var(--green)' : 'var(--red)',
    },
    {
      label: "Today's P&L",
      value: `${(stats.today_pnl || 0) >= 0 ? '+' : ''}$${(stats.today_pnl || 0).toFixed(2)}`,
      sub:   `${stats.today_trades || 0} trades today`,
      color: (stats.today_pnl || 0) >= 0 ? 'var(--green)' : 'var(--red)',
    },
    {
      label: 'Win rate',
      value: `${stats.win_rate || 0}%`,
      sub:   `${stats.wins || 0}W / ${stats.losses || 0}L`,
      color: 'var(--text)',
    },
    {
      label: 'Open positions',
      value: `${openTrades.length} / ${maxPositions}`,
      sub:   `${maxPositions - openTrades.length} slot${maxPositions - openTrades.length !== 1 ? 's' : ''} free`,
      color: openTrades.length >= maxPositions ? 'var(--amber)' : 'var(--text)',
    },
  ]

  return (
    <div style={{
      display: 'grid', gridTemplateColumns: 'repeat(4,1fr)',
      gap: 8, padding: '10px 12px', flexShrink: 0,
    }}>
      {cards.map(c => (
        <div key={c.label} style={{
          background: 'var(--bg-card)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius)', padding: '10px 14px',
        }}>
          <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 4 }}>{c.label}</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: c.color, lineHeight: 1 }}>{c.value}</div>
          <div style={{ fontSize: 11, color: 'var(--text-2)', marginTop: 4 }}>{c.sub}</div>
        </div>
      ))}
    </div>
  )
}
