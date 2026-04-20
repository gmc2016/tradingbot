import React, { useEffect, useRef, useState, useCallback } from 'react'
import { createChart, CrosshairMode } from 'lightweight-charts'
import axios from 'axios'

const TIMEFRAMES = ['15m','1h','4h','1d']

// Map timeframe to Binance WebSocket interval
const TF_WS = { '15m':'15m','1h':'1h','4h':'4h','1d':'1d' }

export default function ChartPanel({ symbol='BTC/USDT', trades=[] }) {
  const containerRef = useRef(null)
  const chartRef     = useRef(null)
  const candleRef    = useRef(null)
  const volRef       = useRef(null)
  const wsRef        = useRef(null)
  const [tf,         setTf]         = useState('1h')
  const [loading,    setLoading]    = useState(false)
  const [lastPrice,  setLastPrice]  = useState(null)
  const [priceChg,   setPriceChg]   = useState(0)
  const [showOB,     setShowOB]     = useState(false)
  const [orderBook,  setOrderBook]  = useState({bids:[],asks:[]})
  const obWsRef = useRef(null)

  // Load historical candles
  const loadData = useCallback(async (sym, timeframe) => {
    setLoading(true)
    try {
      const r = await axios.get('/api/ohlcv', {
        params:{ symbol:sym, timeframe, limit:200 },
        withCredentials:true
      })
      if (!r.data?.length || !candleRef.current) return

      const candles = r.data.map(d => ({
        time:  Math.floor(new Date(d.timestamp).getTime()/1000),
        open:  parseFloat(d.open),  high: parseFloat(d.high),
        low:   parseFloat(d.low),   close:parseFloat(d.close),
      })).filter(d => d.time && !isNaN(d.close)).sort((a,b)=>a.time-b.time)

      const volumes = r.data.map(d => ({
        time:  Math.floor(new Date(d.timestamp).getTime()/1000),
        value: parseFloat(d.volume),
        color: parseFloat(d.close)>=parseFloat(d.open)
               ?'rgba(20,184,166,0.3)':'rgba(239,68,68,0.3)',
      })).filter(d=>d.time&&!isNaN(d.value)).sort((a,b)=>a.time-b.time)

      candleRef.current.setData(candles)
      if (volRef.current) volRef.current.setData(volumes)
      chartRef.current?.timeScale().fitContent()

      if (candles.length>0) {
        const last=candles[candles.length-1]
        const prev=candles[candles.length-2]
        setLastPrice(last.close)
        setPriceChg(prev?((last.close-prev.close)/prev.close*100):0)
      }
    } catch(e) { console.error('Chart load:',e) }
    setLoading(false)
  }, [])

  // Connect to Binance kline WebSocket for live candle updates
  const connectKlineWS = useCallback((sym, timeframe) => {
    if (wsRef.current) wsRef.current.close()
    const stream = sym.replace('/','').toLowerCase()
    const ws     = new WebSocket(`wss://stream.binance.com:9443/ws/${stream}@kline_${TF_WS[timeframe]}`)

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        const k    = data.k
        if (!k || !candleRef.current) return
        const candle = {
          time:  Math.floor(k.t/1000),
          open:  parseFloat(k.o), high:  parseFloat(k.h),
          low:   parseFloat(k.l), close: parseFloat(k.c),
        }
        candleRef.current.update(candle)
        if (volRef.current) volRef.current.update({
          time:  Math.floor(k.t/1000),
          value: parseFloat(k.v),
          color: parseFloat(k.c)>=parseFloat(k.o)
                 ?'rgba(20,184,166,0.3)':'rgba(239,68,68,0.3)',
        })
        setLastPrice(parseFloat(k.c))
        setPriceChg(((parseFloat(k.c)-parseFloat(k.o))/parseFloat(k.o)*100))
      } catch {}
    }
    ws.onerror  = () => setTimeout(()=>connectKlineWS(sym,timeframe), 3000)
    ws.onclose  = () => {}
    wsRef.current = ws
  }, [])

  // Connect to order book WebSocket
  const connectOrderBook = useCallback((sym) => {
    if (obWsRef.current) obWsRef.current.close()
    const stream = sym.replace('/','').toLowerCase()
    const ws     = new WebSocket(`wss://stream.binance.com:9443/ws/${stream}@depth10@100ms`)
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        setOrderBook({
          bids: (data.bids||[]).slice(0,12).map(([p,q])=>({price:parseFloat(p),qty:parseFloat(q)})),
          asks: (data.asks||[]).slice(0,12).map(([p,q])=>({price:parseFloat(p),qty:parseFloat(q)})),
        })
      } catch {}
    }
    ws.onerror = () => setTimeout(()=>connectOrderBook(sym),3000)
    obWsRef.current = ws
  }, [])

  // Init chart
  useEffect(()=>{
    if (!containerRef.current) return
    const chart = createChart(containerRef.current, {
      layout:{ background:{color:'transparent'}, textColor:'#94a3b8' },
      grid:{ vertLines:{color:'rgba(148,163,184,0.08)'}, horzLines:{color:'rgba(148,163,184,0.08)'} },
      crosshair:{ mode:CrosshairMode.Normal },
      rightPriceScale:{ borderColor:'rgba(148,163,184,0.15)' },
      timeScale:{ borderColor:'rgba(148,163,184,0.15)', timeVisible:true, secondsVisible:false },
      width: containerRef.current.clientWidth,
      height:containerRef.current.clientHeight,
    })
    const candles = chart.addCandlestickSeries({
      upColor:'#14b8a6', downColor:'#ef4444',
      borderUpColor:'#14b8a6', borderDownColor:'#ef4444',
      wickUpColor:'#14b8a6', wickDownColor:'#ef4444',
    })
    const vol = chart.addHistogramSeries({
      priceFormat:{type:'volume'}, priceScaleId:'vol',
      scaleMargins:{top:0.85,bottom:0},
    })
    chartRef.current=chart; candleRef.current=candles; volRef.current=vol
    const ro=new ResizeObserver(entries=>{
      const {width,height}=entries[0].contentRect
      chart.applyOptions({width,height})
    })
    ro.observe(containerRef.current)
    return ()=>{ ro.disconnect(); chart.remove(); chartRef.current=null;
                 if(wsRef.current) wsRef.current.close()
                 if(obWsRef.current) obWsRef.current.close() }
  },[])

  // Load + connect WebSocket when symbol/tf changes
  useEffect(()=>{
    if (candleRef.current){ loadData(symbol,tf); connectKlineWS(symbol,tf) }
  },[symbol,tf,loadData,connectKlineWS])

  // Order book WebSocket
  useEffect(()=>{
    if (showOB) connectOrderBook(symbol)
    else if (obWsRef.current){ obWsRef.current.close(); obWsRef.current=null }
  },[showOB,symbol,connectOrderBook])

  // Trade markers
  useEffect(()=>{
    if (!candleRef.current||!trades?.length) return
    const markers=trades
      .filter(t=>t.pair===symbol&&t.entry_price)
      .map(t=>({
        time: Math.floor(new Date(t.opened_at).getTime()/1000),
        position:t.side==='BUY'?'belowBar':'aboveBar',
        color:t.side==='BUY'?'#14b8a6':'#ef4444',
        shape:t.side==='BUY'?'arrowUp':'arrowDown',
        text:`${t.side}${t.pnl!=null?' '+(t.pnl>=0?'+':'')+t.pnl.toFixed(2):''}`,
      }))
      .sort((a,b)=>a.time-b.time)
    if (markers.length) candleRef.current.setMarkers(markers)
  },[trades,symbol])

  const isUp=priceChg>=0
  const fmtPrice=p=>p<0.01?p.toFixed(6):p<1?p.toFixed(4):p<100?p.toFixed(2):p.toLocaleString('en-US',{maximumFractionDigits:2})
  const maxBid=orderBook.bids.length?Math.max(...orderBook.bids.map(b=>b.qty)):1
  const maxAsk=orderBook.asks.length?Math.max(...orderBook.asks.map(a=>a.qty)):1
  const spread=orderBook.asks.length&&orderBook.bids.length
    ?((orderBook.asks[0].price-orderBook.bids[0].price)/orderBook.asks[0].price*100).toFixed(3)
    :null

  return (
    <div style={{flex:1,display:'flex',overflow:'hidden',minHeight:0}}>
      {/* Chart */}
      <div style={{flex:1,display:'flex',flexDirection:'column',overflow:'hidden',minHeight:0}}>
        {/* Header */}
        <div style={{display:'flex',alignItems:'center',gap:10,padding:'5px 12px',
          background:'var(--bg-surface)',borderBottom:'1px solid var(--border)',flexShrink:0}}>
          <span style={{fontWeight:600,fontSize:13}}>{symbol}</span>
          {lastPrice&&<>
            <span style={{fontSize:14,fontWeight:700,fontFamily:'monospace',color:isUp?'var(--green)':'var(--red)'}}>
              {fmtPrice(lastPrice)}
            </span>
            <span style={{fontSize:11,color:isUp?'var(--green)':'var(--red)',fontWeight:500}}>
              {isUp?'+':''}{priceChg.toFixed(2)}%
            </span>
            <span style={{fontSize:10,color:'var(--green)',background:'rgba(20,184,166,.1)',
              padding:'1px 5px',borderRadius:3}}>● LIVE</span>
          </>}
          {loading&&<span style={{fontSize:11,color:'var(--text-3)'}}>loading...</span>}
          <div style={{marginLeft:'auto',display:'flex',gap:4,alignItems:'center'}}>
            {TIMEFRAMES.map(t=>(
              <button key={t} onClick={()=>setTf(t)} style={{
                padding:'2px 8px',borderRadius:4,fontSize:11,fontWeight:tf===t?600:400,
                background:tf===t?'var(--teal)':'transparent',
                color:tf===t?'#fff':'var(--text-2)',border:'none',cursor:'pointer',
              }}>{t}</button>
            ))}
            <button onClick={()=>setShowOB(v=>!v)} style={{
              padding:'2px 8px',borderRadius:4,fontSize:11,
              background:showOB?'rgba(168,85,247,.2)':'transparent',
              color:showOB?'#a855f7':'var(--text-2)',
              border:`1px solid ${showOB?'rgba(168,85,247,.4)':'var(--border)'}`,
              cursor:'pointer',marginLeft:4,
            }}>📊 Order Book</button>
          </div>
        </div>
        <div ref={containerRef} style={{flex:1,minHeight:0}}/>
      </div>

      {/* Order Book Panel */}
      {showOB&&(
        <div style={{width:200,background:'var(--bg-surface)',borderLeft:'1px solid var(--border)',
          display:'flex',flexDirection:'column',flexShrink:0,fontSize:11}}>
          {/* Header */}
          <div style={{padding:'6px 10px',borderBottom:'1px solid var(--border)',flexShrink:0}}>
            <div style={{fontWeight:600,fontSize:11,marginBottom:2}}>Order Book</div>
            {spread&&<div style={{color:'var(--text-3)',fontSize:10}}>Spread: {spread}%</div>}
          </div>

          {/* Column headers */}
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',padding:'4px 8px',
            color:'var(--text-3)',fontSize:10,borderBottom:'1px solid var(--border)',flexShrink:0}}>
            <span>Price</span><span style={{textAlign:'right'}}>Qty</span>
          </div>

          <div style={{flex:1,overflow:'hidden',display:'flex',flexDirection:'column'}}>
            {/* Asks (sell orders) — shown top, lowest ask first */}
            <div style={{flex:1,overflow:'hidden',display:'flex',flexDirection:'column',justifyContent:'flex-end'}}>
              {[...(orderBook.asks||[])].reverse().map((a,i)=>(
                <div key={i} style={{position:'relative',padding:'1px 8px',display:'grid',gridTemplateColumns:'1fr 1fr'}}>
                  <div style={{position:'absolute',right:0,top:0,bottom:0,
                    width:`${(a.qty/maxAsk)*100}%`,background:'rgba(239,68,68,0.12)'}}/>
                  <span style={{color:'var(--red)',fontFamily:'monospace',fontSize:10,zIndex:1}}>{fmtPrice(a.price)}</span>
                  <span style={{textAlign:'right',color:'var(--text-2)',fontFamily:'monospace',fontSize:10,zIndex:1}}>{a.qty.toFixed(3)}</span>
                </div>
              ))}
            </div>

            {/* Mid price */}
            {lastPrice&&(
              <div style={{padding:'4px 8px',background:'var(--bg-hover)',
                borderTop:'1px solid var(--border)',borderBottom:'1px solid var(--border)',
                textAlign:'center',fontWeight:700,fontSize:12,flexShrink:0,
                color:isUp?'var(--green)':'var(--red)'}}>
                {fmtPrice(lastPrice)}
                <span style={{fontSize:9,marginLeft:4,color:isUp?'var(--green)':'var(--red)'}}>
                  {isUp?'▲':'▼'}
                </span>
              </div>
            )}

            {/* Bids (buy orders) */}
            <div style={{flex:1,overflow:'hidden'}}>
              {(orderBook.bids||[]).map((b,i)=>(
                <div key={i} style={{position:'relative',padding:'1px 8px',display:'grid',gridTemplateColumns:'1fr 1fr'}}>
                  <div style={{position:'absolute',right:0,top:0,bottom:0,
                    width:`${(b.qty/maxBid)*100}%`,background:'rgba(20,184,166,0.12)'}}/>
                  <span style={{color:'var(--green)',fontFamily:'monospace',fontSize:10,zIndex:1}}>{fmtPrice(b.price)}</span>
                  <span style={{textAlign:'right',color:'var(--text-2)',fontFamily:'monospace',fontSize:10,zIndex:1}}>{b.qty.toFixed(3)}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Legend */}
          <div style={{padding:'4px 8px',borderTop:'1px solid var(--border)',
            fontSize:9,color:'var(--text-3)',flexShrink:0}}>
            <div style={{color:'var(--red)'}}>▲ Asks = sell orders</div>
            <div style={{color:'var(--green)'}}>▼ Bids = buy orders</div>
          </div>
        </div>
      )}
    </div>
  )
}
