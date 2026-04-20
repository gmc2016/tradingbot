import React, { useEffect, useRef, useState, useCallback } from 'react'
import { createChart, CrosshairMode } from 'lightweight-charts'
import axios from 'axios'
import { io } from 'socket.io-client'

const TIMEFRAMES = ['15m','1h','4h','1d']

export default function ChartPanel({ symbol='BTC/USDT', trades=[] }) {
  const containerRef = useRef(null)
  const chartRef     = useRef(null)
  const candleRef    = useRef(null)
  const volRef       = useRef(null)
  const socketRef    = useRef(null)
  const obWsRef      = useRef(null)
  const [tf,        setTf]       = useState('1h')
  const [loading,   setLoading]  = useState(false)
  const [lastPrice, setLastPrice]= useState(null)
  const [priceChg,  setPriceChg] = useState(0)
  const [showOB,    setShowOB]   = useState(false)
  const [orderBook, setOrderBook]= useState({bids:[],asks:[]})
  const [liveTag,   setLiveTag]  = useState(false)

  const fmtPrice = p =>
    !p ? '—' : p<0.01 ? p.toFixed(6) : p<1 ? p.toFixed(4) :
    p<100 ? p.toFixed(2) : p.toLocaleString('en-US',{maximumFractionDigits:2})

  // Load historical candles via backend REST
  const loadData = useCallback(async (sym, timeframe) => {
    setLoading(true)
    try {
      const r = await axios.get('/api/ohlcv',{
        params:{symbol:sym,timeframe,limit:200},withCredentials:true})
      if (!r.data?.length || !candleRef.current) return

      const candles = r.data
        .map(d=>({time:Math.floor(new Date(d.timestamp).getTime()/1000),
          open:parseFloat(d.open),high:parseFloat(d.high),
          low:parseFloat(d.low),close:parseFloat(d.close)}))
        .filter(d=>d.time&&!isNaN(d.close)).sort((a,b)=>a.time-b.time)

      const volumes = r.data
        .map(d=>({time:Math.floor(new Date(d.timestamp).getTime()/1000),
          value:parseFloat(d.volume),
          color:parseFloat(d.close)>=parseFloat(d.open)
            ?'rgba(20,184,166,0.3)':'rgba(239,68,68,0.3)'}))
        .filter(d=>d.time&&!isNaN(d.value)).sort((a,b)=>a.time-b.time)

      candleRef.current.setData(candles)
      if (volRef.current) volRef.current.setData(volumes)
      chartRef.current?.timeScale().fitContent()

      if (candles.length>0){
        const last=candles[candles.length-1]
        const prev=candles[candles.length-2]
        setLastPrice(last.close)
        setPriceChg(prev?((last.close-prev.close)/prev.close*100):0)
      }
    } catch(e){console.error('Chart load:',e)}
    setLoading(false)
  },[])

  // Tell backend to start kline WebSocket stream for this symbol+tf
  const subscribeKline = useCallback(async (sym, timeframe) => {
    try {
      await axios.post('/api/kline/subscribe',{symbol:sym,timeframe},{withCredentials:true})
    } catch(e){ console.debug('Kline subscribe:',e) }
  },[])

  // Init chart once
  useEffect(()=>{
    if (!containerRef.current) return
    const chart = createChart(containerRef.current,{
      layout:{background:{color:'transparent'},textColor:'#94a3b8'},
      grid:{vertLines:{color:'rgba(148,163,184,0.08)'},horzLines:{color:'rgba(148,163,184,0.08)'}},
      crosshair:{mode:CrosshairMode.Normal},
      rightPriceScale:{borderColor:'rgba(148,163,184,0.15)'},
      timeScale:{borderColor:'rgba(148,163,184,0.15)',timeVisible:true,secondsVisible:false},
      width:containerRef.current.clientWidth,
      height:containerRef.current.clientHeight,
    })
    const candles=chart.addCandlestickSeries({
      upColor:'#14b8a6',downColor:'#ef4444',
      borderUpColor:'#14b8a6',borderDownColor:'#ef4444',
      wickUpColor:'#14b8a6',wickDownColor:'#ef4444',
    })
    const vol=chart.addHistogramSeries({
      priceFormat:{type:'volume'},priceScaleId:'vol',
      scaleMargins:{top:0.85,bottom:0},
    })
    chartRef.current=chart; candleRef.current=candles; volRef.current=vol
    const ro=new ResizeObserver(entries=>{
      const{width,height}=entries[0].contentRect
      chart.applyOptions({width,height})
    })
    ro.observe(containerRef.current)

    // Connect to backend SocketIO for kline updates
    const socket=io({path:'/socket.io',transports:['websocket','polling']})
    socketRef.current=socket
    socket.on('kline_update',({pair,tf:stf,candle})=>{
      if (pair!==symbol||!candleRef.current) return
      try {
        const t = Math.floor(Number(candle.time))  // ensure integer seconds
        candleRef.current.update({
          time:t,open:candle.open,high:candle.high,
          low:candle.low,close:candle.close,
        })
        if (volRef.current) volRef.current.update({
          time:t,value:candle.volume||0,
          color:candle.close>=candle.open?'rgba(20,184,166,0.3)':'rgba(239,68,68,0.3)',
        })
        setLastPrice(candle.close)
        setLiveTag(true)
      } catch(e){ console.debug('kline update:',e) }
    })

    // Also update price from the existing price_update events
    socket.on('price_update',({pair,price,change})=>{
      if (pair===symbol){
        setLastPrice(price); setPriceChg(change)
      }
    })

    return ()=>{
      ro.disconnect(); chart.remove(); chartRef.current=null
      socket.disconnect()
      if (obWsRef.current){ obWsRef.current.close(); obWsRef.current=null }
    }
  // eslint-disable-next-line
  },[])

  // Load data + subscribe kline when symbol or tf changes
  useEffect(()=>{
    if (candleRef.current){
      setLiveTag(false)
      loadData(symbol,tf)
      subscribeKline(symbol,tf)
    }
  },[symbol,tf,loadData,subscribeKline])

  // Update socket listener when symbol changes
  useEffect(()=>{
    if (!socketRef.current) return
    socketRef.current.off('kline_update')
    socketRef.current.on('kline_update',({pair,candle})=>{
      if (pair!==symbol||!candleRef.current) return
      try {
        const t=Math.floor(Number(candle.time))
        candleRef.current.update({time:t,open:candle.open,high:candle.high,low:candle.low,close:candle.close})
        if (volRef.current) volRef.current.update({time:t,value:candle.volume||0,
          color:candle.close>=candle.open?'rgba(20,184,166,0.3)':'rgba(239,68,68,0.3)'})
        setLastPrice(candle.close); setLiveTag(true)
      } catch(e){ console.debug('kline:',e) }
    })
  },[symbol])

  // Order book via direct Binance WS (depth data, not blocked by CSP usually)
  const connectOB = useCallback((sym)=>{
    if (obWsRef.current){ obWsRef.current.close(); obWsRef.current=null }
    const stream=sym.replace('/','').toLowerCase()
    try {
      const ws=new WebSocket(`wss://stream.binance.com:9443/ws/${stream}@depth10@100ms`)
      ws.onmessage=(e)=>{
        try {
          const d=JSON.parse(e.data)
          setOrderBook({
            bids:(d.bids||[]).slice(0,12).map(([p,q])=>({price:parseFloat(p),qty:parseFloat(q)})),
            asks:(d.asks||[]).slice(0,12).map(([p,q])=>({price:parseFloat(p),qty:parseFloat(q)})),
          })
        } catch{}
      }
      ws.onerror=()=>setTimeout(()=>connectOB(sym),3000)
      obWsRef.current=ws
    } catch(e){ console.debug('OB WS:',e) }
  },[])

  useEffect(()=>{
    if (showOB) connectOB(symbol)
    else if (obWsRef.current){ obWsRef.current.close(); obWsRef.current=null }
  },[showOB,symbol,connectOB])

  // Trade markers
  useEffect(()=>{
    if (!candleRef.current||!trades?.length) return
    const markers=trades
      .filter(t=>t.pair===symbol&&t.entry_price)
      .map(t=>({
        time:Math.floor(new Date(t.opened_at).getTime()/1000),
        position:t.side==='BUY'?'belowBar':'aboveBar',
        color:t.side==='BUY'?'#14b8a6':'#ef4444',
        shape:t.side==='BUY'?'arrowUp':'arrowDown',
        text:`${t.side}${t.pnl!=null?' '+(t.pnl>=0?'+':'')+t.pnl.toFixed(2):''}`,
      }))
      .sort((a,b)=>a.time-b.time)
    if (markers.length) candleRef.current.setMarkers(markers)
  },[trades,symbol])

  const isUp=priceChg>=0
  const maxBid=orderBook.bids.length?Math.max(...orderBook.bids.map(b=>b.qty)):1
  const maxAsk=orderBook.asks.length?Math.max(...orderBook.asks.map(a=>a.qty)):1
  const spread=orderBook.asks.length&&orderBook.bids.length
    ?((orderBook.asks[0].price-orderBook.bids[0].price)/orderBook.asks[0].price*100).toFixed(3)
    :null

  return (
    <div style={{flex:1,display:'flex',overflow:'hidden',minHeight:0}}>
      <div style={{flex:1,display:'flex',flexDirection:'column',overflow:'hidden',minHeight:0}}>
        {/* Chart header */}
        <div style={{display:'flex',alignItems:'center',gap:10,padding:'5px 12px',
          background:'var(--bg-surface)',borderBottom:'1px solid var(--border)',flexShrink:0}}>
          <span style={{fontWeight:600,fontSize:13}}>{symbol}</span>
          {lastPrice&&<>
            <span style={{fontSize:14,fontWeight:700,fontFamily:'monospace',
              color:isUp?'var(--green)':'var(--red)'}}>
              {fmtPrice(lastPrice)}
            </span>
            <span style={{fontSize:11,color:isUp?'var(--green)':'var(--red)',fontWeight:500}}>
              {isUp?'+':''}{typeof priceChg==='number'?priceChg.toFixed(2):'0.00'}%
            </span>
            <span style={{fontSize:10,color:liveTag?'var(--green)':'var(--text-3)',
              background:liveTag?'rgba(20,184,166,.1)':'transparent',
              padding:'1px 5px',borderRadius:3,transition:'all .3s'}}>
              {liveTag?'● LIVE':'◌ loading...'}
            </span>
          </>}
          {loading&&<span style={{fontSize:11,color:'var(--text-3)'}}>fetching candles...</span>}
          <div style={{marginLeft:'auto',display:'flex',gap:4,alignItems:'center'}}>
            {TIMEFRAMES.map(t=>(
              <button key={t} onClick={()=>setTf(t)} style={{
                padding:'2px 8px',borderRadius:4,fontSize:11,fontWeight:tf===t?600:400,
                background:tf===t?'var(--teal)':'transparent',
                color:tf===t?'#fff':'var(--text-2)',border:'none',cursor:'pointer',
              }}>{t}</button>
            ))}
            <button onClick={()=>setShowOB(v=>!v)} style={{
              padding:'2px 8px',borderRadius:4,fontSize:11,marginLeft:4,
              background:showOB?'rgba(168,85,247,.2)':'transparent',
              color:showOB?'#a855f7':'var(--text-2)',
              border:`1px solid ${showOB?'rgba(168,85,247,.4)':'var(--border)'}`,
              cursor:'pointer',
            }}>📊 Order Book</button>
          </div>
        </div>
        <div ref={containerRef} style={{flex:1,minHeight:0}}/>
      </div>

      {/* Order Book */}
      {showOB&&(
        <div style={{width:200,background:'var(--bg-surface)',borderLeft:'1px solid var(--border)',
          display:'flex',flexDirection:'column',flexShrink:0,fontSize:11}}>
          <div style={{padding:'6px 10px',borderBottom:'1px solid var(--border)',flexShrink:0}}>
            <div style={{fontWeight:600,fontSize:11,marginBottom:2}}>Order Book</div>
            {spread&&<div style={{color:'var(--text-3)',fontSize:10}}>Spread: {spread}%</div>}
          </div>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',padding:'3px 8px',
            color:'var(--text-3)',fontSize:10,borderBottom:'1px solid var(--border)',flexShrink:0}}>
            <span>Price (USDT)</span><span style={{textAlign:'right'}}>Amount</span>
          </div>
          <div style={{flex:1,overflow:'hidden',display:'flex',flexDirection:'column'}}>
            {/* Asks - sell orders (red) reversed so lowest is at bottom */}
            <div style={{flex:1,display:'flex',flexDirection:'column',justifyContent:'flex-end',overflow:'hidden'}}>
              {[...(orderBook.asks||[])].reverse().map((a,i)=>(
                <div key={i} style={{position:'relative',padding:'1px 8px',
                  display:'grid',gridTemplateColumns:'1fr 1fr'}}>
                  <div style={{position:'absolute',right:0,top:0,bottom:0,
                    width:`${Math.min((a.qty/maxAsk)*100,100)}%`,
                    background:'rgba(239,68,68,0.15)'}}/>
                  <span style={{color:'var(--red)',fontFamily:'monospace',fontSize:10,position:'relative'}}>
                    {fmtPrice(a.price)}
                  </span>
                  <span style={{textAlign:'right',color:'var(--text-2)',fontFamily:'monospace',
                    fontSize:10,position:'relative'}}>
                    {a.qty.toFixed(3)}
                  </span>
                </div>
              ))}
            </div>
            {/* Spread / mid price */}
            {lastPrice&&(
              <div style={{padding:'4px 8px',background:'var(--bg-hover)',
                border:'1px solid var(--border)',textAlign:'center',
                fontWeight:700,fontSize:12,flexShrink:0,
                color:isUp?'var(--green)':'var(--red)'}}>
                {fmtPrice(lastPrice)} {isUp?'▲':'▼'}
              </div>
            )}
            {/* Bids - buy orders (green) */}
            <div style={{flex:1,overflow:'hidden'}}>
              {(orderBook.bids||[]).map((b,i)=>(
                <div key={i} style={{position:'relative',padding:'1px 8px',
                  display:'grid',gridTemplateColumns:'1fr 1fr'}}>
                  <div style={{position:'absolute',right:0,top:0,bottom:0,
                    width:`${Math.min((b.qty/maxBid)*100,100)}%`,
                    background:'rgba(20,184,166,0.15)'}}/>
                  <span style={{color:'var(--green)',fontFamily:'monospace',fontSize:10,position:'relative'}}>
                    {fmtPrice(b.price)}
                  </span>
                  <span style={{textAlign:'right',color:'var(--text-2)',fontFamily:'monospace',
                    fontSize:10,position:'relative'}}>
                    {b.qty.toFixed(3)}
                  </span>
                </div>
              ))}
            </div>
          </div>
          <div style={{padding:'4px 8px',borderTop:'1px solid var(--border)',
            fontSize:9,color:'var(--text-3)',flexShrink:0,lineHeight:1.6}}>
            <span style={{color:'var(--red)'}}>▲ Asks</span> = sell orders waiting<br/>
            <span style={{color:'var(--green)'}}>▼ Bids</span> = buy orders waiting<br/>
            Thick bar = large order = support/resistance
          </div>
        </div>
      )}
    </div>
  )
}
