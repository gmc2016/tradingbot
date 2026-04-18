import React from 'react'
import { SignalBadge } from './Tooltip'

export default function Sidebar({ pairs = [], selectedPair, onSelectPair, balance, config, mode }) {
  return (
    <div style={{
      width: 210, flexShrink: 0,
      background: 'var(--bg-surface)',
      borderRight: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column',
      overflow: 'hidden',
    }}>
      {/* Balance */}
      <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
        <div style={{ fontSize: 10, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: .5, marginBottom: 4 }}>
          USDT Balance
        </div>
        <div style={{ fontSize: 22, fontWeight: 700 }}>
          ${(balance || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-3)', marginTop: 2 }}>
          {mode === 'demo' ? 'Paper balance' : 'Live balance'}
        </div>
      </div>

      {/* Pairs list */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
        <div style={{ padding: '0 14px', fontSize: 10, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: .5, marginBottom: 6 }}>
          Pairs
        </div>
        {pairs.map(p => (
          <PairRow key={p.symbol} pair={p} selected={selectedPair === p.symbol} onClick={() => onSelectPair(p.symbol)} />
        ))}
      </div>

      {/* Strategy summary */}
      <div style={{ padding: '10px 14px', borderTop: '1px solid var(--border)', flexShrink: 0 }}>
        <div style={{ fontSize: 10, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: .5, marginBottom: 8 }}>
          Strategy
        </div>
        {[
          ['SL',   `${config?.stop_loss_pct || '—'}%`,   'var(--red)'],
          ['TP',   `${config?.take_profit_pct || '—'}%`, 'var(--green)'],
          ['Size', `$${config?.position_size_usdt || '—'}`, null],
          ['Max',  `${config?.max_positions || '—'} pos`, null],
        ].map(([l, v, c]) => (
          <div key={l} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span style={{ fontSize: 11, color: 'var(--text-2)' }}>{l}</span>
            <span style={{ fontSize: 11, fontWeight: 600, color: c || 'var(--text)' }}>{v}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function PairRow({ pair, selected, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '7px 14px', cursor: 'pointer',
        background: selected ? 'var(--bg-hover)' : 'transparent',
        borderLeft: selected ? '2px solid var(--teal)' : '2px solid transparent',
        transition: 'background .1s',
      }}
      onMouseEnter={e => !selected && (e.currentTarget.style.background = 'var(--bg-hover)')}
      onMouseLeave={e => !selected && (e.currentTarget.style.background = 'transparent')}
    >
      <div>
        <div style={{ fontWeight: 600, fontSize: 13 }}>
          {pair.symbol.replace('/USDT', '')}
          <span style={{ color: 'var(--text-3)', fontWeight: 400 }}>/USDT</span>
        </div>
        <div style={{ fontSize: 11, color: (pair.change || 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>
          {(pair.change || 0) >= 0 ? '+' : ''}{(pair.change || 0).toFixed(2)}%
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 3 }}>
        <SignalBadge signal={p.signal} confidence={p.confidence}/>
        {pair.confidence > 0 && (
          <span style={{ fontSize: 10, color: 'var(--text-3)' }}>{pair.confidence}%</span>
        )}
      </div>
    </div>
  )
}
