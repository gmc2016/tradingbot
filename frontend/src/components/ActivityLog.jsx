import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import { io } from 'socket.io-client'

const CATEGORIES = [
  { id:'all',      label:'All',      color:'var(--text-2)' },
  { id:'trade',    label:'Trades',   color:'var(--green)'  },
  { id:'signal',   label:'Signals',  color:'var(--blue)'   },
  { id:'ai',       label:'AI',       color:'#a855f7'       },
  { id:'brain',    label:'Brain',    color:'#ec4899'       },
  { id:'settings', label:'Settings', color:'var(--amber)'  },
  { id:'scanner',  label:'Scanner',  color:'var(--teal)'   },
  { id:'system',   label:'System',   color:'var(--text-3)' },
]

const CAT_STYLES = {
  trade:    { color:'var(--green)',  bg:'var(--green-bg)'                },
  signal:   { color:'var(--blue)',   bg:'var(--blue-bg)'                 },
  ai:       { color:'#a855f7',       bg:'rgba(168,85,247,.12)'           },
  brain:    { color:'#ec4899',       bg:'rgba(236,72,153,.12)'           },
  settings: { color:'var(--amber)',  bg:'var(--amber-bg)'                },
  scanner:  { color:'var(--teal)',   bg:'rgba(20,184,166,.12)'           },
  system:   { color:'var(--text-3)', bg:'var(--bg-hover)'                },
}

const LEVEL_STYLES = {
  success: { color:'var(--green)', icon:'✓' },
  warning: { color:'var(--amber)', icon:'⚠' },
  error:   { color:'var(--red)',   icon:'✗' },
  info:    { color:'var(--text-2)',icon:'·' },
}

function formatTS(iso) {
  if (!iso) return ''
  const d = new Date(iso + 'Z')
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString(undefined, { hour:'2-digit', minute:'2-digit', second:'2-digit' })
}

export default function ActivityLog({ onClose }) {
  const [logs,       setLogs]       = useState([])
  const [category,   setCategory]   = useState('all')
  const [autoScroll, setAutoScroll] = useState(true)
  const [paused,     setPaused]     = useState(false)
  const [search,     setSearch]     = useState('')
  const [dateFrom,   setDateFrom]   = useState('')
  const [dateTo,     setDateTo]     = useState('')
  const [expanded,   setExpanded]   = useState(null)
  const bottomRef = useRef(null)
  const socketRef = useRef(null)

  const load = async (cat='all') => {
    try {
      const r = await axios.get('/api/activity', {
        params: { category: cat, limit: 200, date_from: dateFrom||undefined, date_to: dateTo||undefined },
        withCredentials: true
      })
      setLogs(r.data.reverse()) // oldest first for display
    } catch(e) {}
  }

  useEffect(() => {
    load(category)
    // Connect to live updates via socket
    const socket = io({ path: '/socket.io', transports: ['websocket', 'polling'] })
    socketRef.current = socket
    socket.on('activity_update', (entry) => {
      if (!paused) {
        setLogs(prev => {
          if (category !== 'all' && entry.category !== category) return prev
          return [...prev.slice(-199), entry]
        })
      }
    })
    return () => socket.disconnect()
  }, [category])

  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, autoScroll])

  const filtered = search
    ? logs.filter(l => l.message?.toLowerCase().includes(search.toLowerCase()))
    : logs

  return (
    <div style={{position:'fixed',inset:0,background:'var(--bg-base)',zIndex:500,display:'flex',flexDirection:'column'}}>

      {/* Header */}
      <div style={{height:48,background:'var(--bg-surface)',borderBottom:'1px solid var(--border)',display:'flex',alignItems:'center',gap:12,padding:'0 16px',flexShrink:0}}>
        <button onClick={onClose} style={{color:'var(--text-2)',fontSize:18}}>←</button>
        <span style={{fontWeight:600,fontSize:15}}>Live Activity Log</span>
          <button onClick={()=>window.open('/api/export/activity','_blank')} style={{padding:'3px 10px',border:'1px solid var(--teal)',borderRadius:5,fontSize:11,color:'var(--teal)',background:'rgba(20,184,166,.1)'}}>
            ↓ Export CSV
          </button>
        <div style={{width:8,height:8,borderRadius:'50%',background:paused?'var(--amber)':'var(--green)',
          boxShadow:paused?'none':'0 0 6px var(--green)'}}/>
        <span style={{fontSize:11,color:'var(--text-3)'}}>{paused?'Paused':'Live'}</span>
        <span style={{fontSize:11,color:'var(--text-3)',marginLeft:4}}>{filtered.length} entries</span>
      </div>

      {/* Filter bar */}
      <div style={{background:'var(--bg-surface)',borderBottom:'1px solid var(--border)',padding:'6px 14px',display:'flex',alignItems:'center',gap:8,flexShrink:0,flexWrap:'wrap'}}>
        {/* Category tabs */}
        <div style={{display:'flex',gap:4,flexWrap:'wrap'}}>
          {CATEGORIES.map(c => (
            <button key={c.id} onClick={() => { setCategory(c.id); load(c.id) }} style={{
              padding:'3px 10px',borderRadius:20,fontSize:11,fontWeight:category===c.id?600:400,
              background:category===c.id?'var(--bg-hover)':'transparent',
              color:category===c.id?c.color:'var(--text-3)',
              border:category===c.id?`1px solid ${c.color}`:'1px solid transparent',
            }}>{c.label}</button>
          ))}
        </div>

        <input type="date" value={dateFrom} onChange={e=>{setDateFrom(e.target.value);load(category)}}
          style={{fontSize:11,padding:'3px 6px'}} title="From date"/>
        <span style={{color:'var(--text-3)',fontSize:11}}>→</span>
        <input type="date" value={dateTo} onChange={e=>{setDateTo(e.target.value);load(category)}}
          style={{fontSize:11,padding:'3px 6px'}} title="To date"/>
        <div style={{flex:1,minWidth:140}}>
          <input placeholder="Search..." value={search} onChange={e=>setSearch(e.target.value)}
            style={{fontSize:11,padding:'4px 8px'}}/>
        </div>

        <div style={{display:'flex',gap:6,marginLeft:'auto'}}>
          <button onClick={()=>setPaused(p=>!p)} style={{
            padding:'4px 10px',borderRadius:4,fontSize:11,
            background:paused?'var(--amber-bg)':'var(--bg-hover)',
            border:`1px solid ${paused?'var(--amber)':'var(--border)'}`,
            color:paused?'var(--amber)':'var(--text-2)',
          }}>{paused?'▶ Resume':'⏸ Pause'}</button>
          <button onClick={()=>setAutoScroll(a=>!a)} style={{
            padding:'4px 10px',borderRadius:4,fontSize:11,
            background:autoScroll?'var(--blue-bg)':'var(--bg-hover)',
            border:`1px solid ${autoScroll?'var(--blue)':'var(--border)'}`,
            color:autoScroll?'var(--blue)':'var(--text-2)',
          }}>↓ Auto-scroll {autoScroll?'ON':'OFF'}</button>
          <button onClick={()=>load(category)} style={{
            padding:'4px 10px',borderRadius:4,fontSize:11,
            border:'1px solid var(--border)',color:'var(--text-2)',
          }}>↻ Refresh</button>
        </div>
      </div>

      {/* Log entries */}
      <div style={{flex:1,overflowY:'auto',padding:'8px 0',fontFamily:'monospace'}}>
        {filtered.length===0 && (
          <div style={{textAlign:'center',padding:40,color:'var(--text-3)',fontSize:13,fontFamily:'inherit'}}>
            No activity yet — start the bot to see live decisions
          </div>
        )}
        {filtered.map((entry, i) => {
          const cat   = CAT_STYLES[entry.category] || CAT_STYLES.system
          const lvl   = LEVEL_STYLES[entry.level]  || LEVEL_STYLES.info
          const isExp = expanded === entry.id
          let detail  = null
          try { if (entry.detail) detail = JSON.parse(entry.detail) } catch {}

          return (
            <div key={entry.id || i}
              onClick={() => setExpanded(isExp ? null : entry.id)}
              style={{
                display:'flex', alignItems:'flex-start', gap:8,
                padding:'4px 14px', cursor: detail ? 'pointer' : 'default',
                borderBottom:'1px solid var(--border-dim)',
                background: isExp ? 'var(--bg-hover)' : 'transparent',
              }}
              onMouseEnter={e => e.currentTarget.style.background='var(--bg-hover)'}
              onMouseLeave={e => e.currentTarget.style.background=isExp?'var(--bg-hover)':'transparent'}
            >
              {/* Timestamp */}
              <span style={{fontSize:10,color:'var(--text-3)',whiteSpace:'nowrap',paddingTop:2,minWidth:130}}>
                {formatTS(entry.ts)}
              </span>

              {/* Category badge */}
              <span style={{
                fontSize:9,fontWeight:700,padding:'2px 5px',borderRadius:3,
                background:cat.bg,color:cat.color,whiteSpace:'nowrap',
                textTransform:'uppercase',letterSpacing:.5,flexShrink:0,paddingTop:3,
              }}>{entry.category}</span>

              {/* Level icon */}
              <span style={{fontSize:12,color:lvl.color,flexShrink:0,width:12}}>{lvl.icon}</span>

              {/* Message + detail */}
              <div style={{flex:1,minWidth:0}}>
                <span style={{fontSize:12,color:lvl.color==='var(--text-2)'?'var(--text)':lvl.color,lineHeight:1.5}}>
                  {entry.message}
                </span>
                {detail && isExp && (
                  <div style={{
                    marginTop:6,padding:'8px 10px',borderRadius:4,
                    background:'var(--bg-card)',border:'1px solid var(--border)',
                    fontSize:11,color:'var(--text-2)',lineHeight:1.7,
                  }}>
                    {Object.entries(detail).map(([k,v]) => (
                      <div key={k} style={{display:'flex',gap:8}}>
                        <span style={{color:'var(--text-3)',minWidth:120,flexShrink:0}}>{k}:</span>
                        <span style={{
                          color: k==='pnl' ? (v>=0?'var(--green)':'var(--red)')
                               : k==='approved' ? (v?'var(--green)':'var(--red)')
                               : 'var(--text)',
                          wordBreak:'break-all',
                        }}>
                          {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
                {detail && !isExp && (
                  <span style={{fontSize:10,color:'var(--text-3)',marginLeft:6}}>▸ click for details</span>
                )}
              </div>
            </div>
          )
        })}
        <div ref={bottomRef}/>
      </div>

      {/* Footer legend */}
      <div style={{background:'var(--bg-surface)',borderTop:'1px solid var(--border)',padding:'6px 14px',display:'flex',gap:16,flexShrink:0}}>
        {Object.entries(LEVEL_STYLES).map(([level, s]) => (
          <span key={level} style={{fontSize:11,color:s.color}}>{s.icon} {level}</span>
        ))}
        <span style={{marginLeft:'auto',fontSize:11,color:'var(--text-3)'}}>
          Click any entry with "▸ click for details" to expand
        </span>
      </div>
    </div>
  )
}
