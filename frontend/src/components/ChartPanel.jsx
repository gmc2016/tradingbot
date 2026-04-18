import React, { useEffect, useRef, useState, useCallback } from 'react'
import { createChart, CrosshairMode, LineStyle } from 'lightweight-charts'
import axios from 'axios'

const TIMEFRAMES = ['15m','1h','4h','1d']

export default function ChartPanel({ symbol = 'BTC/USDT', trades = [] }) {
  const containerRef = useRef(null)
  const chartRef     = useRef(null)
  const candleRef    = useRef(null)
  const volRef       = useRef(null)
  const [tf, setTf]  = useState('1h')
  const [loading, setLoading] = useState(false)
  const [lastPrice, setLastPrice] = useState(null)
  const [priceChange, setPriceChange] = useState(0)

  const loadData = useCallback(async (sym, timeframe) => {
    setLoading(true)
    try {
      const limit = timeframe === '15m' ? 200 : timeframe === '1h' ? 200 : 150
      const r = await axios.get('/api/ohlcv', {
        params: { symbol: sym, timeframe, limit },
        withCredentials: true
      })
      const raw = r.data
      if (!raw?.length || !candleRef.current) return

      const candles = raw.map(d => ({
        time:  Math.floor(new Date(d.timestamp).getTime() / 1000),
        open:  parseFloat(d.open),
        high:  parseFloat(d.high),
        low:   parseFloat(d.low),
        close: parseFloat(d.close),
      })).filter(d => d.time && !isNaN(d.close))
        .sort((a,b) => a.time - b.time)

      const volumes = raw.map(d => ({
        time:  Math.floor(new Date(d.timestamp).getTime() / 1000),
        value: parseFloat(d.volume),
        color: parseFloat(d.close) >= parseFloat(d.open)
          ? 'rgba(20,184,166,0.3)' : 'rgba(239,68,68,0.3)',
      })).filter(d => d.time && !isNaN(d.value))
        .sort((a,b) => a.time - b.time)

      candleRef.current.setData(candles)
      if (volRef.current) volRef.current.setData(volumes)
      chartRef.current?.timeScale().fitContent()

      if (candles.length > 0) {
        const last = candles[candles.length - 1]
        const prev = candles[candles.length - 2]
        setLastPrice(last.close)
        setPriceChange(prev ? ((last.close - prev.close) / prev.close * 100) : 0)
      }
    } catch(e) {
      console.error('Chart load error:', e)
    }
    setLoading(false)
  }, [])

  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: 'transparent' },
        textColor:  '#94a3b8',
      },
      grid: {
        vertLines: { color: 'rgba(148,163,184,0.08)' },
        horzLines: { color: 'rgba(148,163,184,0.08)' },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: 'rgba(148,163,184,0.15)' },
      timeScale: {
        borderColor: 'rgba(148,163,184,0.15)',
        timeVisible: true, secondsVisible: false,
      },
      width:  containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
    })

    const candles = chart.addCandlestickSeries({
      upColor:   '#14b8a6',
      downColor: '#ef4444',
      borderUpColor:   '#14b8a6',
      borderDownColor: '#ef4444',
      wickUpColor:   '#14b8a6',
      wickDownColor: '#ef4444',
    })

    const vol = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: 'vol',
      scaleMargins: { top: 0.85, bottom: 0 },
    })

    chartRef.current = chart
    candleRef.current = candles
    volRef.current = vol

    const ro = new ResizeObserver(entries => {
      const { width, height } = entries[0].contentRect
      chart.applyOptions({ width, height })
    })
    ro.observe(containerRef.current)

    return () => { ro.disconnect(); chart.remove(); chartRef.current = null }
  }, [])

  // Load data when symbol or timeframe changes
  useEffect(() => {
    if (candleRef.current) loadData(symbol, tf)
  }, [symbol, tf, loadData])

  // Auto-refresh candles every 30 seconds for live feel
  useEffect(() => {
    const interval = setInterval(() => {
      if (candleRef.current) loadData(symbol, tf)
    }, 30000)
    return () => clearInterval(interval)
  }, [symbol, tf, loadData])

  // Draw trade markers
  useEffect(() => {
    if (!candleRef.current || !trades?.length) return
    const markers = trades
      .filter(t => t.pair === symbol && t.entry_price)
      .map(t => {
        const ts = Math.floor(new Date(t.opened_at).getTime() / 1000)
        return {
          time:     ts,
          position: t.side === 'BUY' ? 'belowBar' : 'aboveBar',
          color:    t.side === 'BUY' ? '#14b8a6' : '#ef4444',
          shape:    t.side === 'BUY' ? 'arrowUp' : 'arrowDown',
          text:     `${t.side} ${t.pnl != null ? (t.pnl >= 0 ? '+' : '') + t.pnl.toFixed(2) : ''}`,
        }
      })
      .sort((a,b) => a.time - b.time)
    if (markers.length) candleRef.current.setMarkers(markers)
  }, [trades, symbol])

  const isUp = priceChange >= 0

  return (
    <div style={{flex:1,display:'flex',flexDirection:'column',overflow:'hidden',minHeight:0,position:'relative'}}>
      {/* Chart header */}
      <div style={{
        display:'flex',alignItems:'center',gap:12,padding:'6px 12px',
        background:'var(--bg-surface)',borderBottom:'1px solid var(--border)',flexShrink:0,
      }}>
        <span style={{fontWeight:600,fontSize:13}}>{symbol}</span>
        {lastPrice&&<>
          <span style={{fontSize:14,fontWeight:700,fontFamily:'monospace'}}>
            {lastPrice < 0.01 ? lastPrice.toFixed(6)
              : lastPrice < 1 ? lastPrice.toFixed(4)
              : lastPrice < 100 ? lastPrice.toFixed(2)
              : lastPrice.toLocaleString('en-US',{maximumFractionDigits:2})}
          </span>
          <span style={{fontSize:12,color:isUp?'var(--green)':'var(--red)',fontWeight:500}}>
            {isUp?'+':''}{priceChange.toFixed(2)}%
          </span>
        </>}
        {loading&&<span style={{fontSize:11,color:'var(--text-3)'}}>loading...</span>}
        <div style={{marginLeft:'auto',display:'flex',gap:4}}>
          {TIMEFRAMES.map(t=>(
            <button key={t} onClick={()=>setTf(t)} style={{
              padding:'2px 8px',borderRadius:4,fontSize:11,fontWeight:tf===t?600:400,
              background:tf===t?'var(--teal)':'transparent',
              color:tf===t?'#fff':'var(--text-2)',border:'none',cursor:'pointer',
            }}>{t}</button>
          ))}
          <button onClick={()=>loadData(symbol,tf)} title="Refresh chart" style={{
            padding:'2px 8px',borderRadius:4,fontSize:11,color:'var(--text-2)',
            background:'transparent',border:'none',cursor:'pointer',
          }}>↻</button>
        </div>
      </div>
      <div ref={containerRef} style={{flex:1,minHeight:0}}/>
    </div>
  )
}
