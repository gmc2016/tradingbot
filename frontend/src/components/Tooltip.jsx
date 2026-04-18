import React, { useState, useRef, useEffect } from 'react'

const SIGNAL_INFO = {
  BUY:  'BUY signal — bot sees bullish conditions. Price likely moving up. Bot may open or already has a long position.',
  SELL: 'SELL signal — bot sees bearish conditions. Price likely moving down. Bot may open or already has a short/sell position.',
  HOLD: 'HOLD — no clear signal. Conditions not strong enough to trade. Bot is watching but not acting.',
}

const TERM_INFO = {
  'SL': 'Stop-Loss — if price moves this far against the trade, it closes automatically to limit losses.',
  'TP': 'Take-Profit — when price reaches this level, the trade closes to lock in profit.',
  'ADX': 'Average Directional Index — measures trend strength (0-100). Above 25 = strong trend. Below 20 = ranging/choppy.',
  'RSI': 'Relative Strength Index — momentum indicator (0-100). Below 35 = oversold (may bounce up). Above 65 = overbought (may drop).',
  'ATR': 'Average True Range — measures market volatility. Higher = bigger price swings. Used to set stop-loss distance.',
  'PnL': 'Profit and Loss — how much money this trade made (positive) or lost (negative) in USDT.',
  'Donchian': 'Donchian Channel — tracks the highest high and lowest low over N candles. A breakout above the top signals a BUY, below the bottom signals a SELL.',
  'Confluence': 'RSI + MACD + Bollinger Bands strategy — requires multiple indicators to agree before trading. Higher win rate but smaller gains.',
  'MTF': 'Multi-Timeframe — signal must appear on both 1-hour and 4-hour charts to trade. Fewer trades, higher quality.',
  'Combined': 'All strategies run simultaneously. Trades when any fires. If multiple agree, confidence is boosted.',
}

export function Tooltip({ text, children, delay=1500 }) {
  const [visible, setVisible] = useState(false)
  const [pos, setPos] = useState({x:0, y:0})
  const timerRef = useRef(null)
  const ref = useRef(null)

  const show = (e) => {
    const r = e.currentTarget.getBoundingClientRect()
    setPos({ x: r.left, y: r.bottom + 4 })
    timerRef.current = setTimeout(() => setVisible(true), delay)
  }
  const hide = () => {
    clearTimeout(timerRef.current)
    setVisible(false)
  }

  return (
    <span ref={ref} onMouseEnter={show} onMouseLeave={hide} style={{position:'relative',display:'inline-block'}}>
      {children}
      {visible&&(
        <div style={{
          position:'fixed', left: Math.min(pos.x, window.innerWidth-240), top: pos.y,
          zIndex:9999, background:'#1e293b', border:'1px solid #334155',
          borderRadius:6, padding:'8px 10px', maxWidth:230,
          fontSize:11, color:'#cbd5e1', lineHeight:1.5, pointerEvents:'none',
          boxShadow:'0 4px 16px rgba(0,0,0,.5)',
        }}>
          {text}
        </div>
      )}
    </span>
  )
}

export function SignalBadge({ signal, confidence }) {
  const info = SIGNAL_INFO[signal] || ''
  const colors = {
    BUY:  { bg:'var(--green-bg)', color:'var(--green)',  border:'var(--green-dim)' },
    SELL: { bg:'var(--red-bg)',   color:'var(--red)',    border:'var(--red-dim)'   },
    HOLD: { bg:'var(--bg-hover)', color:'var(--text-3)', border:'var(--border)'    },
  }
  const c = colors[signal] || colors.HOLD

  return (
    <Tooltip text={info} delay={1500}>
      <span style={{
        fontSize:10, fontWeight:600, padding:'2px 7px', borderRadius:10,
        background:c.bg, color:c.color, border:`1px solid ${c.border}`,
        cursor:'help', display:'inline-block',
      }}>
        {signal}{confidence>0&&signal!=='HOLD'?` ${confidence}%`:''}
      </span>
    </Tooltip>
  )
}

export function TermTooltip({ term, children }) {
  const info = TERM_INFO[term]
  if (!info) return children
  return <Tooltip text={info} delay={800}>{children}</Tooltip>
}
