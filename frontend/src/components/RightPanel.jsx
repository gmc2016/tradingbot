import React from 'react'

function formatPrice(p){ if(!p)return'—'; if(p>1000)return p.toLocaleString('en-US',{maximumFractionDigits:0}); if(p>1)return p.toFixed(3); return p.toFixed(5) }
function timeAgo(iso){ if(!iso)return''; const m=Math.floor((Date.now()-new Date(iso).getTime())/60000); if(m<1)return'just now'; if(m<60)return`${m}m ago`; return`${Math.floor(m/60)}h ago` }

export default function RightPanel({ openTrades=[], pairs=[], news=[], config={}, prices={} }) {
  return (
    <div style={{width:270,flexShrink:0,background:'var(--bg-surface)',borderLeft:'1px solid var(--border)',display:'flex',flexDirection:'column',overflow:'hidden'}}>

      <Section title={`Open positions (${openTrades.length})`}>
        {openTrades.length===0
          ? <Empty>No open positions</Empty>
          : openTrades.map(t=><PositionCard key={t.id} trade={t} config={config} prices={prices}/>)}
      </Section>

      <Section title="AI Sentiment">
        {pairs.slice(0,8).map(p=><SentimentRow key={p.symbol} symbol={p.symbol} score={p.sentiment??50}/>)}
      </Section>

      <Section title="Latest news" flex>
        <div style={{overflowY:'auto',flex:1}}>
          {news.length===0
            ? <Empty>No news yet — click Refresh news</Empty>
            : news.map(n=><NewsItem key={n.id} item={n}/>)}
        </div>
      </Section>
    </div>
  )
}

function Section({title,children,flex}){
  return <div style={{padding:'10px 12px',borderBottom:'1px solid var(--border)',...(flex?{flex:1,display:'flex',flexDirection:'column',minHeight:0,overflow:'hidden'}:{})}}>
    <div style={{fontSize:10,color:'var(--text-3)',textTransform:'uppercase',letterSpacing:.5,fontWeight:600,marginBottom:8}}>{title}</div>
    {children}
  </div>
}
function Empty({children}){ return <div style={{fontSize:12,color:'var(--text-3)'}}>{children}</div> }

function PositionCard({trade:t, config, prices={}}){
  const pnl = t.unrealized_pnl??t.pnl
  const c   = pnl==null?'var(--text-2)':pnl>=0?'var(--green)':'var(--red)'
  const pnlPct = t.entry_price ? ((pnl||0)/(t.entry_price*t.quantity)*100).toFixed(1) : 0
  const isTrailing = !!t.trailing_stop

  return (
    <div style={{background:'var(--bg-card)',border:`1px solid ${pnl!=null&&pnl>=0?'rgba(34,197,94,.2)':'var(--border)'}`,borderRadius:6,padding:'8px 10px',marginBottom:6}}>
      <div style={{display:'flex',justifyContent:'space-between',marginBottom:4}}>
        <span style={{fontWeight:600}}>{t.pair}</span>
        <div style={{textAlign:'right'}}>
          <span style={{fontWeight:700,color:c}}>{pnl==null?'—':`${pnl>=0?'+':''}$${pnl.toFixed(2)}`}</span>
          {pnl!=null&&<span style={{fontSize:10,color:c,marginLeft:4}}>({pnlPct}%)</span>}
        </div>
      </div>
      <div style={{display:'flex',justifyContent:'space-between',marginBottom:4}}>
        <span style={{fontSize:11,color:'var(--text-3)'}}>Entry</span>
        <span style={{fontSize:11,fontFamily:'monospace',color:'var(--text-2)'}}>{formatPrice(t.entry_price)}</span>
      </div>
      {prices[t.pair] && (
        <div style={{display:'flex',justifyContent:'space-between',marginBottom:4}}>
          <span style={{fontSize:11,color:'var(--text-3)'}}>Current</span>
          <span style={{fontSize:12,fontFamily:'monospace',fontWeight:700,
            color:(prices[t.pair].price > t.entry_price && t.side==='BUY') ||
                  (prices[t.pair].price < t.entry_price && t.side==='SELL')
                  ? 'var(--green)' : 'var(--red)'}}>
            {formatPrice(prices[t.pair].price)}
            <span style={{fontSize:9,marginLeft:3,color:(prices[t.pair].change||0)>=0?'var(--green)':'var(--red)'}}>
              {(prices[t.pair].change||0)>=0?'▲':'▼'}{Math.abs(prices[t.pair].change||0).toFixed(2)}%
            </span>
          </span>
        </div>
      )}
      <div style={{display:'flex',justifyContent:'space-between',marginBottom:6}}>
        <span style={{fontSize:10,color:'var(--text-3)'}}>{t.strategy_reason?.includes('Scalp')?'⚡ Scalp':'🧠 Smart'}</span>
        <span className={`badge badge-${(t.side||'').toLowerCase()}`}>{t.side}</span>
      </div>
      <div style={{display:'flex',gap:5,flexWrap:'wrap'}}>
        <Tag label={`SL ${formatPrice(t.stop_loss)}`}   bg="var(--red-bg)"   color="var(--red)"/>
        <Tag label={`TP ${formatPrice(t.take_profit)}`} bg="var(--green-bg)" color="var(--green)"/>
        {isTrailing && <Tag label="Trailing ✓" bg="var(--blue-bg)" color="var(--blue)"/>}
      </div>
    </div>
  )
}

function Tag({label,bg,color}){
  return <span style={{fontSize:10,padding:'2px 6px',borderRadius:10,background:bg,color,fontWeight:500}}>{label}</span>
}

function SentimentRow({symbol,score}){
  const coin=symbol.replace('/USDT',''),pct=Math.round(score)
  const c=pct>=55?'var(--green)':pct<=45?'var(--red)':'var(--amber)'
  return <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:5}}>
    <span style={{fontSize:11,color:'var(--text-2)',width:36}}>{coin}</span>
    <div style={{flex:1,height:4,background:'var(--bg-hover)',borderRadius:2,overflow:'hidden'}}>
      <div style={{width:`${pct}%`,height:'100%',background:c,borderRadius:2,transition:'width .4s'}}/>
    </div>
    <span style={{fontSize:11,fontWeight:600,color:c,width:32,textAlign:'right'}}>{pct}%</span>
  </div>
}

function NewsItem({item}){
  const s=item.sentiment==='bullish'?'bull':item.sentiment==='bearish'?'bear':'neutral'
  return <div style={{paddingBottom:8,marginBottom:8,borderBottom:'1px solid var(--border-dim)'}}>
    <div style={{fontSize:12,lineHeight:1.4,marginBottom:4}}>{item.title}</div>
    <div style={{display:'flex',alignItems:'center',gap:6}}>
      <span style={{fontSize:10,color:'var(--text-3)'}}>{timeAgo(item.fetched_at)}</span>
      <span className={`badge badge-${s}`}>{item.sentiment}</span>
      {item.source&&<span style={{fontSize:10,color:'var(--text-3)'}}>{item.source}</span>}
    </div>
  </div>
}
