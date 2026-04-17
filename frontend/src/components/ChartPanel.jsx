import React, { useEffect, useRef, useState, useCallback } from 'react'
import { createChart } from 'lightweight-charts'
import { fetchOHLCV } from '../hooks/useDashboard'

const TFS = ['15m', '1h', '4h', '1d']

export default function ChartPanel({ symbol = 'BTC/USDT', trades = [] }) {
  const containerRef = useRef(null)
  const chartRef     = useRef(null)
  const seriesRef    = useRef(null)
  const [tf, setTf]  = useState('1h')
  const [loading, setLoading] = useState(false)

  const loadData = useCallback(async (sym, timeframe) => {
    if (!seriesRef.current) return
    setLoading(true)
    try {
      const candles = await fetchOHLCV(sym, timeframe, 200)
      if (!candles?.length) return
      const formatted = candles
        .map(c => ({ time: Math.floor(new Date(c.timestamp).getTime() / 1000), open: c.open, high: c.high, low: c.low, close: c.close }))
        .sort((a, b) => a.time - b.time)
      seriesRef.current.setData(formatted)

      const markers = trades
        .filter(t => t.pair === sym)
        .map(t => ({
          time:     Math.floor(new Date(t.opened_at).getTime() / 1000),
          position: t.side === 'BUY' ? 'belowBar' : 'aboveBar',
          color:    t.side === 'BUY' ? '#22c55e'  : '#ef4444',
          shape:    t.side === 'BUY' ? 'arrowUp'  : 'arrowDown',
          text:     t.side,
        }))
        .filter(m => m.time > 0)
        .sort((a, b) => a.time - b.time)
      seriesRef.current.setMarkers(markers)
      chartRef.current?.timeScale().fitContent()
    } catch (e) {
      console.error('Chart load error:', e)
    } finally {
      setLoading(false)
    }
  }, [trades])

  // Create chart once
  useEffect(() => {
    if (!containerRef.current) return
    const chart = createChart(containerRef.current, {
      layout:    { background: { color: 'transparent' }, textColor: '#8899b4' },
      grid:      { vertLines: { color: '#1e2d47' }, horzLines: { color: '#1e2d47' } },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: '#2a3550' },
      timeScale:       { borderColor: '#2a3550', timeVisible: true, secondsVisible: false },
      width:  containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
    })
    const series = chart.addCandlestickSeries({
      upColor:        '#22c55e', downColor:        '#ef4444',
      borderUpColor:  '#22c55e', borderDownColor:  '#ef4444',
      wickUpColor:    '#22c55e', wickDownColor:    '#ef4444',
    })
    chartRef.current  = chart
    seriesRef.current = series

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth, height: containerRef.current.clientHeight })
      }
    })
    ro.observe(containerRef.current)
    return () => { ro.disconnect(); chart.remove() }
  }, [])

  // Reload when symbol or timeframe changes
  useEffect(() => { loadData(symbol, tf) }, [symbol, tf, loadData])

  return (
    <div style={{
      flex: 1, minHeight: 0, margin: '0 12px',
      background: 'var(--bg-card)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius)', display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '8px 12px', borderBottom: '1px solid var(--border)', flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontWeight: 600 }}>{symbol}</span>
          {loading && <span style={{ fontSize: 11, color: 'var(--text-3)' }}>Loading...</span>}
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          {TFS.map(t => (
            <button key={t} onClick={() => setTf(t)} style={{
              padding: '3px 9px', borderRadius: 4, fontSize: 11,
              fontWeight:  tf === t ? 600 : 400,
              background:  tf === t ? 'var(--bg-hover)' : 'transparent',
              color:       tf === t ? 'var(--text)'     : 'var(--text-2)',
              border:      tf === t ? '1px solid var(--border)' : '1px solid transparent',
            }}>{t}</button>
          ))}
        </div>
      </div>
      <div ref={containerRef} style={{ flex: 1, minHeight: 0 }} />
    </div>
  )
}
