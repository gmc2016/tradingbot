import React, { useState } from 'react'
import { useDashboard } from './hooks/useDashboard'
import Topbar        from './components/Topbar'
import Sidebar       from './components/Sidebar'
import KpiBar        from './components/KpiBar'
import ChartPanel    from './components/ChartPanel'
import TradesTable   from './components/TradesTable'
import RightPanel    from './components/RightPanel'
import SettingsModal from './components/SettingsModal'
import HistoryPage   from './components/HistoryPage'

export default function App() {
  const { data, connected, prices, startBot, stopBot, setMode, runNow, refreshNews, updateSettings } = useDashboard()
  const [selectedPair,  setSelectedPair]  = useState('BTC/USDT')
  const [showSettings,  setShowSettings]  = useState(false)
  const [showHistory,   setShowHistory]   = useState(false)

  const handleModeChange = (mode) => {
    if (mode === 'live') {
      const ok = window.confirm('⚠️ Switch to LIVE mode?\n\nThis will execute REAL orders on Binance with REAL funds.\n\nMake sure API keys are configured correctly.\n\nProceed?')
      if (!ok) return
    }
    setMode(mode)
  }

  if (!data) {
    return (
      <div style={{display:'flex',alignItems:'center',justifyContent:'center',height:'100vh',flexDirection:'column',gap:12}}>
        <div style={{width:32,height:32,border:'3px solid var(--border)',borderTopColor:'var(--teal)',borderRadius:'50%',animation:'spin .8s linear infinite'}}/>
        <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
        <div style={{fontSize:14,color:'var(--text-2)'}}>Connecting to Trading Bot...</div>
      </div>
    )
  }

  const { stats, open_trades=[], recent_trades=[], news=[], mode, bot_running, usdt_balance, config={} } = data

  const pairs = (data.pairs || []).map(p => ({
    ...p,
    price:  prices[p.symbol]?.price  ?? p.price,
    change: prices[p.symbol]?.change ?? p.change,
  }))

  return (
    <div style={{display:'flex',flexDirection:'column',height:'100vh',overflow:'hidden'}}>

      <Topbar data={{...data,pairs}} connected={connected} onStart={startBot} onStop={stopBot} onModeChange={handleModeChange} />

      {/* Action bar */}
      <div style={{background:'var(--bg-surface)',borderBottom:'1px solid var(--border)',padding:'4px 12px',display:'flex',alignItems:'center',gap:8,flexShrink:0}}>
        {[
          ['⚡ Run cycle now', runNow],
          ['📰 Refresh news',  refreshNews],
          ['📋 History',       () => setShowHistory(true)],
          ['⚙ Settings',      () => setShowSettings(true)],
        ].map(([label, fn]) => (
          <button key={label} onClick={fn}
            style={{padding:'4px 12px',border:'1px solid var(--border)',borderRadius:5,color:'var(--text-2)'}}
            onMouseEnter={e=>{e.currentTarget.style.background='var(--bg-hover)';e.currentTarget.style.color='var(--text)'}}
            onMouseLeave={e=>{e.currentTarget.style.background='transparent';e.currentTarget.style.color='var(--text-2)'}}
          >{label}</button>
        ))}
        <span style={{marginLeft:'auto',fontSize:11,color:'var(--text-3)'}}>
          Prices: real-time · Signals: every 5 min · News: every 15 min
        </span>
        {data.last_update && (
          <span style={{fontSize:11,color:'var(--text-3)'}}>
            Signals {new Date(data.last_update).toLocaleTimeString()}
          </span>
        )}
      </div>

      {/* Body */}
      <div style={{flex:1,display:'flex',overflow:'hidden',minHeight:0}}>
        <Sidebar pairs={pairs} selectedPair={selectedPair} onSelectPair={setSelectedPair}
                 balance={usdt_balance} config={config} mode={mode} />
        <div style={{flex:1,display:'flex',flexDirection:'column',overflow:'hidden',minHeight:0}}>
          <KpiBar stats={stats} openTrades={open_trades} maxPositions={config.max_positions||5} />
          <ChartPanel symbol={selectedPair} trades={recent_trades} />
          <TradesTable trades={recent_trades} mode={mode} />
        </div>
        <RightPanel openTrades={open_trades} pairs={pairs} news={news} config={config} />
      </div>

      {showSettings && (
        <SettingsModal config={config} onSave={updateSettings} onClose={()=>setShowSettings(false)} />
      )}

      {showHistory && <HistoryPage onClose={()=>setShowHistory(false)} />}
    </div>
  )
}
