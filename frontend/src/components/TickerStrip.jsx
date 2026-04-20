import React, { useRef } from 'react'

export default function TickerStrip({ pairs=[], watchlist=[], prices={}, onSelectPair }) {
  const ref = useRef(null)

  // Combine active pairs + watchlist, deduplicate
  const seen = new Set()
  const all  = [...pairs, ...watchlist].filter(p => {
    const sym = p.symbol || p
    if (seen.has(sym)) return false
    seen.add(sym)
    return true
  }).map(p => {
    const sym    = p.symbol || p
    const live   = prices[sym]
    const price  = live?.price  ?? p.price  ?? 0
    const change = live?.change ?? p.change ?? 0
    return {
      symbol:    sym,
      price,
      change,
      signal:    p.signal    || '--',
      confidence:p.confidence|| 0,
      sentiment: p.sentiment || 50,
      inActive:  pairs.some(ap => (ap.symbol||ap) === sym),
      autoPromote: p.auto_promote || false,
    }
  })

  const fmtPrice = p =>
    !p ? '—' : p < 0.001 ? p.toFixed(6) : p < 1 ? p.toFixed(4) :
    p < 100 ? p.toFixed(2) : p >= 1000
      ? p.toLocaleString('en-US',{maximumFractionDigits:0})
      : p.toFixed(2)

  return (
    <div style={{
      background:'var(--bg-surface)',borderBottom:'1px solid var(--border)',
      overflowX:'auto',flexShrink:0,
    }} ref={ref}>
      <div style={{display:'flex',alignItems:'center',minWidth:'max-content',padding:'0 8px'}}>
        {all.map(p => {
          const isUp = p.change >= 0
          const hasSig = p.signal !== 'HOLD' && p.signal !== '--'
          const sigColor = p.signal === 'BUY' ? 'var(--green)' : p.signal === 'SELL' ? 'var(--red)' : 'var(--text-3)'

          return (
            <div key={p.symbol}
              onClick={() => onSelectPair && onSelectPair(p.symbol)}
              style={{
                display:'flex',alignItems:'center',gap:6,padding:'5px 12px',
                borderRight:'1px solid var(--border)',cursor:'pointer',
                minWidth:0,flexShrink:0,transition:'background .15s',
                background: p.autoPromote ? 'rgba(20,184,166,.06)' : 'transparent',
              }}
              onMouseEnter={e=>e.currentTarget.style.background='var(--bg-hover)'}
              onMouseLeave={e=>e.currentTarget.style.background=p.autoPromote?'rgba(20,184,166,.06)':'transparent'}
            >
              {/* Coin name */}
              <span style={{
                fontSize:11,fontWeight:600,
                color: p.inActive ? 'var(--text)' : 'var(--text-3)',
                whiteSpace:'nowrap',
              }}>
                {p.symbol.replace('/USDT','')}
                {!p.inActive && <span style={{fontSize:9,color:'var(--text-3)',marginLeft:2}}>●</span>}
              </span>

              {/* Price */}
              <span style={{fontSize:11,fontFamily:'monospace',color:'var(--text)',whiteSpace:'nowrap'}}>
                ${fmtPrice(p.price)}
              </span>

              {/* Change % */}
              <span style={{
                fontSize:10,fontWeight:500,whiteSpace:'nowrap',
                color:isUp?'var(--green)':'var(--red)',
              }}>
                {isUp?'▲':'▼'}{Math.abs(p.change).toFixed(2)}%
              </span>

              {/* Signal badge - only if non-HOLD */}
              {hasSig && (
                <span style={{
                  fontSize:9,fontWeight:700,padding:'1px 5px',borderRadius:8,
                  background:p.signal==='BUY'?'var(--green-bg)':'var(--red-bg)',
                  color:sigColor,whiteSpace:'nowrap',
                }}>
                  {p.signal} {p.confidence}%
                </span>
              )}

              {/* Auto-promote indicator */}
              {p.autoPromote && (
                <span style={{fontSize:9,color:'var(--teal)',fontWeight:600}}>↑</span>
              )}
            </div>
          )
        })}

        {all.length === 0 && (
          <div style={{padding:'5px 12px',fontSize:11,color:'var(--text-3)'}}>
            Loading ticker...
          </div>
        )}
      </div>
    </div>
  )
}
