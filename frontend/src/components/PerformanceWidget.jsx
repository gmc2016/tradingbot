import React, { useState, useEffect } from 'react'
import axios from 'axios'

export default function PerformanceWidget() {
  const [perf, setPerf]   = useState(null)
  const [loading, setLoad] = useState(true)

  const load = async () => {
    try {
      const r = await axios.get('/api/performance', { withCredentials: true })
      setPerf(r.data)
    } catch(e) {}
    setLoad(false)
  }

  useEffect(() => { load(); const t = setInterval(load, 60000); return ()=>clearInterval(t) }, [])

  const unflag = async (pair) => {
    await axios.post('/api/performance/unflag', { pair }, { withCredentials: true })
    load()
  }

  if (loading || !perf) return null

  const profitColor = perf.profit_pct >= 0 ? 'var(--green)' : 'var(--red)'
  const todayColor  = perf.today_pnl  >= 0 ? 'var(--green)' : 'var(--red)'
  const floorPct    = perf.balance ? ((perf.balance - perf.floor_balance) / perf.balance * 100).toFixed(1) : 0

  return (
    <div style={{ background:'var(--bg-surface)', borderTop:'1px solid var(--border)', padding:'8px 14px', flexShrink:0 }}>
      <div style={{ display:'flex', alignItems:'center', gap:16, flexWrap:'wrap' }}>

        {/* Balance + profit */}
        <div style={{ display:'flex', alignItems:'center', gap:6 }}>
          <span style={{ fontSize:10, color:'var(--text-3)' }}>Balance</span>
          <span style={{ fontSize:13, fontWeight:700 }}>${(perf.balance||0).toFixed(2)}</span>
          <span style={{ fontSize:10, fontWeight:600, color:profitColor }}>
            {perf.profit_pct >= 0 ? '+' : ''}{perf.profit_pct}%
          </span>
        </div>

        <div style={{ width:1, height:20, background:'var(--border)' }}/>

        {/* Today */}
        <div style={{ display:'flex', alignItems:'center', gap:6 }}>
          <span style={{ fontSize:10, color:'var(--text-3)' }}>Today</span>
          <span style={{ fontSize:12, fontWeight:600, color:todayColor }}>
            {perf.today_pnl >= 0 ? '+' : ''}${(perf.today_pnl||0).toFixed(2)}
          </span>
          <span style={{ fontSize:10, color:'var(--text-3)' }}>
            {perf.today_wins||0}/{perf.today_trades||0} wins
          </span>
        </div>

        <div style={{ width:1, height:20, background:'var(--border)' }}/>

        {/* Week */}
        <div style={{ display:'flex', alignItems:'center', gap:6 }}>
          <span style={{ fontSize:10, color:'var(--text-3)' }}>7 days</span>
          <span style={{ fontSize:12, fontWeight:600,
            color:(perf.week_pnl||0)>=0?'var(--green)':'var(--red)' }}>
            {(perf.week_pnl||0)>=0?'+':''}${(perf.week_pnl||0).toFixed(2)}
          </span>
        </div>

        <div style={{ width:1, height:20, background:'var(--border)' }}/>

        {/* Capital protection floor */}
        <div style={{ display:'flex', alignItems:'center', gap:6 }}>
          <span style={{ fontSize:10, color:'var(--text-3)' }}>Floor</span>
          <span style={{ fontSize:11, color:'var(--text-2)' }}>${(perf.floor_balance||0).toFixed(0)}</span>
          <span style={{ fontSize:10,
            color: parseFloat(floorPct) > 5 ? 'var(--green)' : 'var(--amber)' }}>
            {floorPct}% above floor
          </span>
        </div>

        {/* Best/worst pair */}
        {perf.best_pair && (
          <>
            <div style={{ width:1, height:20, background:'var(--border)' }}/>
            <div style={{ display:'flex', alignItems:'center', gap:4 }}>
              <span style={{ fontSize:10, color:'var(--text-3)' }}>Best 7d</span>
              <span style={{ fontSize:10, color:'var(--green)', fontWeight:600 }}>
                {perf.best_pair.pair?.replace('/USDT','')} +${perf.best_pair.total_pnl}
              </span>
            </div>
          </>
        )}

        {/* Flagged pairs */}
        {perf.flagged_pairs?.length > 0 && (
          <>
            <div style={{ width:1, height:20, background:'var(--border)' }}/>
            <div style={{ display:'flex', alignItems:'center', gap:4, flexWrap:'wrap' }}>
              <span style={{ fontSize:10, color:'var(--text-3)' }}>⚑ Flagged</span>
              {perf.flagged_pairs.map(p => (
                <span key={p} style={{ fontSize:10, color:'var(--red)',
                  background:'var(--red-bg)', padding:'1px 6px', borderRadius:8,
                  display:'flex', alignItems:'center', gap:3 }}>
                  {p.replace('/USDT','')}
                  <button onClick={()=>unflag(p)} style={{
                    fontSize:9, color:'var(--text-3)', background:'none',
                    border:'none', cursor:'pointer', padding:0, lineHeight:1,
                  }} title="Un-flag and re-enable">×</button>
                </span>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
