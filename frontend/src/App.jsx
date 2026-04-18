import React, { useState } from 'react'
import { useAuth, useDashboard } from './hooks/useDashboard'
import LoginPage      from './components/LoginPage'
import Topbar         from './components/Topbar'
import Sidebar        from './components/Sidebar'
import KpiBar         from './components/KpiBar'
import ChartPanel     from './components/ChartPanel'
import TradesTable    from './components/TradesTable'
import RightPanel     from './components/RightPanel'
import SettingsModal  from './components/SettingsModal'
import HistoryPage    from './components/HistoryPage'
import ManualTrade    from './components/ManualTrade'
import HelpPage       from './components/HelpPage'
import ScannerPanel  from './components/ScannerPanel'
import AccountPage   from './components/AccountPage'
import BrainPanel    from './components/BrainPanel'
import ActivityLog   from './components/ActivityLog'

function Dashboard({ auth, logout }) {
  const { data, connected, prices, startBot, stopBot, setMode, runNow, refreshNews, updateSettings } = useDashboard()
  const [selectedPair,  setSelectedPair]  = useState('BTC/USDT')
  const [showSettings,  setShowSettings]  = useState(false)
  const [showHistory,   setShowHistory]   = useState(false)
  const [showTrade,     setShowTrade]     = useState(false)
  const [showHelp,      setShowHelp]      = useState(false)
  const [showScanner,   setShowScanner]   = useState(false)
  const [showAccount,   setShowAccount]   = useState(false)
  const [showBrain,     setShowBrain]     = useState(false)
  const [showActivity,  setShowActivity]  = useState(false)

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
        <div style={{fontSize:14,color:'var(--text-2)'}}>Loading dashboard...</div>
      </div>
    )
  }

  const { stats, open_trades=[], recent_trades=[], news=[], mode, bot_running, usdt_balance, config={} } = data

  const pairs = (data.pairs || []).map(p => ({
    ...p,
    price:  prices[p.symbol]?.price  ?? p.price,
    change: prices[p.symbol]?.change ?? p.change,
  }))

  const actionBtns = [
    ['⚡ Run now',       runNow],
    ['📰 Refresh news',  refreshNews],
    ['🖐 Trade',         () => setShowTrade(true)],
    ['📋 History',       () => setShowHistory(true)],
    ['⚙ Settings',      () => setShowSettings(true)],
    ['❓ Help',          () => setShowHelp(true)],
    ['🔍 Scan pairs',    () => setShowScanner(true)],
    ['💰 Account',       () => setShowAccount(true)],
    ['🧠 AI Brain',      () => setShowBrain(true)],
    ['📡 Activity',      () => setShowActivity(true)],
  ]

  return (
    <div style={{display:'flex',flexDirection:'column',height:'100vh',overflow:'hidden'}}>
      <Topbar data={{...data,pairs}} connected={connected} onStart={startBot} onStop={stopBot} onModeChange={handleModeChange}/>

      <div style={{background:'var(--bg-surface)',borderBottom:'1px solid var(--border)',padding:'4px 12px',display:'flex',alignItems:'center',gap:6,flexShrink:0}}>
        {actionBtns.map(([label,fn])=>(
          <button key={label} onClick={fn}
            style={{padding:'4px 11px',border:'1px solid var(--border)',borderRadius:5,color:'var(--text-2)',fontSize:11}}
            onMouseEnter={e=>{e.currentTarget.style.background='var(--bg-hover)';e.currentTarget.style.color='var(--text)'}}
            onMouseLeave={e=>{e.currentTarget.style.background='transparent';e.currentTarget.style.color='var(--text-2)'}}
          >{label}</button>
        ))}
        <span style={{marginLeft:'auto',fontSize:11,color:'var(--text-3)',display:'flex',alignItems:'center',gap:8}}>
          {config.strategy_mode&&<span style={{color:'var(--teal)'}}>
            {config.strategy_mode==='combined'?'🔀':config.strategy_mode==='donchian'?'📊':config.strategy_mode==='mtf'?'🕐':'📈'} {config.strategy_mode}
          </span>}
          {config.use_llm_filter==='true'&&config.anthropic_key_set
            ?<span style={{background:'rgba(168,85,247,.15)',border:'1px solid rgba(168,85,247,.3)',borderRadius:10,padding:'1px 7px',color:'#a855f7',fontWeight:600}}>🤖 AI active</span>
            :<span style={{background:'var(--bg-hover)',borderRadius:10,padding:'1px 7px',color:'var(--text-3)'}}>AI off</span>
          }
          <span>Prices: real-time · Signals: 5 min</span>
        </span>
        {data.last_update&&<span style={{fontSize:11,color:'var(--text-3)'}}>Updated {new Date(data.last_update).toLocaleTimeString()}</span>}
      </div>

      <div style={{flex:1,display:'flex',overflow:'hidden',minHeight:0}}>
        <Sidebar pairs={pairs} selectedPair={selectedPair} onSelectPair={setSelectedPair} balance={usdt_balance} config={config} mode={mode}/>
        <div style={{flex:1,display:'flex',flexDirection:'column',overflow:'hidden',minHeight:0}}>
          <KpiBar stats={stats} openTrades={open_trades} maxPositions={config.max_positions||5}/>
          <ChartPanel symbol={selectedPair} trades={recent_trades}/>
          <TradesTable trades={recent_trades} mode={mode}/>
        </div>
        <RightPanel openTrades={open_trades} pairs={pairs} news={news} config={config}/>
      </div>

      {showSettings&&<SettingsModal config={config} onSave={updateSettings} onClose={()=>setShowSettings(false)} onLogout={logout} username={auth?.username||'admin'}/>}
      {showHistory&&<HistoryPage onClose={()=>setShowHistory(false)}/>}
      {showHelp&&<HelpPage onClose={()=>setShowHelp(false)}/>}
      {showScanner&&<ScannerPanel config={config} onClose={()=>setShowScanner(false)} onPairsUpdated={()=>runNow()}/>}
      {showAccount&&<AccountPage onClose={()=>setShowAccount(false)}/>}
      {showBrain&&<BrainPanel config={config} onClose={()=>setShowBrain(false)}/>}
      {showActivity&&<ActivityLog onClose={()=>setShowActivity(false)}/>}
      {showTrade&&(
        <ManualTrade
          pairs={pairs}
          openTrades={open_trades}
          mode={mode}
          onClose={()=>setShowTrade(false)}
          onDone={()=>{ runNow(); }}
        />
      )}
    </div>
  )
}

export default function App() {
  const { auth, login, logout } = useAuth()
  if (auth===null) {
    return (
      <div style={{display:'flex',alignItems:'center',justifyContent:'center',height:'100vh'}}>
        <div style={{width:24,height:24,border:'2px solid var(--border)',borderTopColor:'var(--teal)',borderRadius:'50%',animation:'spin .8s linear infinite'}}/>
        <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
      </div>
    )
  }
  if (!auth) return <LoginPage onLogin={login}/>
  return <Dashboard auth={auth} logout={logout}/>
}
