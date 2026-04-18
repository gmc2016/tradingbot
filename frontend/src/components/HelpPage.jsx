import React, { useState } from 'react'

const SECTIONS = [
  {
    id: 'overview',
    title: '📈 How the bot works',
    content: `The Trading Bot is a fully automated crypto trading system running 24/7 on your NAS. It connects to Binance, analyzes market data, reads news, and opens/closes trades automatically — all without you needing to be online.

Your browser is just a dashboard. Closing it does not stop the bot. The bot lives inside a Docker container on your NAS and keeps running regardless.

**Architecture:**
• Backend (Python) — runs the trading logic, talks to Binance, manages the database
• Frontend (React) — the dashboard you see in your browser
• Nginx — routes traffic between frontend and backend
• SQLite — stores all trades, settings, and news

**Data flow every 5 minutes:**
1. Fetch live candle data (OHLCV) from Binance for each pair
2. Run technical analysis (RSI, MACD, Bollinger Bands, ADX, ATR, Donchian)
3. Fetch and analyze recent news headlines
4. If LLM (Claude AI) is configured — ask it whether to proceed with the trade
5. Open trade if signal confidence ≥ 55%
6. Monitor all open trades for stop-loss / take-profit / trailing stop`
  },
  {
    id: 'start_stop',
    title: '▶ Start bot / Stop bot',
    content: `The Start/Stop button is a master switch for trade execution.

**Bot STOPPED:**
• Prices still update in real-time
• Signals are still calculated and shown
• Charts and news still work
• NO new trades will be opened
• Existing open trades are still monitored and will close at SL/TP

**Bot RUNNING:**
• Every 5 minutes, scans all active pairs for signals
• Opens trades automatically when signal confidence ≥ 55%
• Manages open positions (partial close, trailing stop, SL/TP)

Use "Stop" when you want to watch signals without risking money, or before making major settings changes.`
  },
  {
    id: 'run_now',
    title: '⚡ Run cycle now',
    content: `Triggers one immediate scan cycle without waiting for the 5-minute timer.

Use this when:
• You just changed settings and want to see them take effect immediately
• You want to check if any signals are currently firing
• You switched strategy mode and want to see new signals right away

It does exactly the same thing as the automatic cycle — scans all pairs, checks signals, opens trades if conditions are met.`
  },
  {
    id: 'strategies',
    title: '📊 Trading strategies',
    content: `The bot has 4 strategies. You choose the mode in Settings → Strategy.

**Combined (recommended)**
Runs all strategies simultaneously. Trades when any strategy fires. If multiple strategies agree on the same direction, confidence is boosted. Best overall performance.

**Donchian Channel Breakout**
Based on a strategy that achieved 43.8% APR in real trading (documented by Joe Tay, 2025). The Donchian Channel tracks the highest high and lowest low over N candles. When price breaks above the upper channel → BUY. When it breaks below the lower channel → SELL.
• Win rate: ~35% (lower than other strategies)
• But winning trades are 2× larger than losing trades (1:2 risk/reward)
• Stop-loss and take-profit are set automatically based on ATR (market volatility)
• Only trades when ADX > 18 (filters out ranging/choppy markets)
• Lookback period adapts: high volatility = shorter lookback, low volatility = longer

**RSI + MACD + Bollinger Bands (Confluence)**
Multi-indicator strategy requiring at least 4 weighted points to fire:
• RSI < 35 = BUY (+2), RSI > 65 = SELL (+2)
• MACD crossover = ±2, MACD direction = ±1
• Price vs Bollinger Bands = ±1 to ±2
• EMA 50/200 trend = ±1
• News sentiment = ±1
Higher win rate (~60%) but smaller gains per trade.

**EMA 9/21 Crossover**
Classic trend-following strategy:
• EMA 9 crosses above EMA 21 → BUY (Golden Cross)
• EMA 9 crosses below EMA 21 → SELL (Death Cross)
Only fires when ADX > 20. ATR-based SL/TP.

**Multi-Timeframe (MTF)**
The most selective strategy. Requires the 1-hour signal to be confirmed by the 4-hour chart. If both timeframes agree → trade. If they disagree → HOLD.
• Highest win rate (~65%) but fewer trades
• Confidence is boosted when both timeframes agree`
  },
  {
    id: 'llm',
    title: '🤖 AI / LLM intelligence',
    content: `The bot uses Claude AI (claude-haiku) as a second opinion before opening trades. This requires your Anthropic API key in Settings → API Keys.

**How it works:**

1. Technical strategy fires a BUY or SELL signal
2. Before executing, the bot sends to Claude:
   • The signal direction and confidence
   • RSI, ADX, market regime
   • Recent news headlines for that coin
   • News sentiment score
3. Claude evaluates whether to proceed and returns:
   • approved: true/false
   • adjusted_confidence: 0-100
   • reasoning: one-sentence explanation
   • risk_level: low/medium/high

**What Claude checks:**
• Does the news contradict the technical signal? (e.g. BUY signal but major hack just announced)
• Are there high-risk macro events (Fed meetings, regulatory news)?
• Is sentiment aligned with the trade direction?
• Has the news already been priced in?

**Without Anthropic key:**
The LLM step is skipped entirely and the bot trades purely on technical signals. Everything still works, just without the AI layer.

**News sentiment analysis:**
• With Anthropic key: Claude reads headlines and scores them -1.0 to +1.0, discounting already-priced-in news. Blended 70% LLM / 30% VADER.
• Without key: VADER (rule-based positive/negative word counting) provides a simpler score.`
  },
  {
    id: 'risk',
    title: '🛡 Risk management',
    content: `**Stop-loss**
Maximum loss per trade. If price moves against you by this %, the trade closes automatically.
• For Donchian/EMA/MTF strategies: stop-loss is set at 1.5× ATR from entry (adapts to volatility)
• For confluence strategy: uses your configured stop-loss %

**Take-profit**
Target profit per trade. When price reaches this level, the trade closes.
• Donchian/EMA/MTF: set at 2.0–2.5× ATR (always larger than stop-loss for positive expectancy)
• Confluence: uses your configured take-profit %

**Partial close**
When a trade is up by your configured % (default +1.5%), the bot automatically closes a portion (default 50%) to lock in profit. The remaining position continues running with a trailing stop.
Example: Buy BTC at $100 → price reaches $101.50 → sell 50% at $101.50 (locking $0.75 profit) → remaining 50% runs with trailing stop.

**Trailing stop**
Once a trade is in profit, the stop-loss automatically follows the price upward, staying X% below the highest price reached. The stop only moves in the profitable direction — never against you.
Example: Buy BTC at $100, trailing stop 0.8% → price hits $105 → stop moves to $104.16 → if price drops to $104.16 the trade closes locking in $4.16 profit.

**Agno-style loss protection**
After N consecutive losses on the same pair (default: 3), that pair is paused for a cooldown period (default: 60 minutes). Prevents the bot from chasing losses on a pair that is trending strongly against it. A cooldown indicator shows on the pair in the sidebar.

**Max positions**
The bot will never open more than this many trades simultaneously. Prevents over-exposure.`
  },
  {
    id: 'manual',
    title: '🖐 Manual trading',
    content: `Click the "Trade" button in the action bar to open the manual trade panel.

**Opening a manual trade:**
1. Select the pair (e.g. BTC/USDT)
2. Choose direction: BUY (you expect price to go up) or SELL (you expect price to go down)
3. Set the USDT amount to risk
4. Set stop-loss % and take-profit %
5. The preview shows your estimated entry, SL price, TP price, max loss, and target gain
6. Click Buy/Sell to execute immediately at market price

The trade is recorded in history alongside bot trades. All risk management (trailing stop, partial close) applies to manual trades too.

**Closing a position early:**
In the manual trade panel → "Close position" tab, you can force-close any open position at the current market price, regardless of whether SL/TP has been hit.

**Demo vs Live:**
Manual trades respect the current mode setting (Demo/Live shown in the panel header).`
  },
  {
    id: 'history',
    title: '📋 Trade history',
    content: `Click "History" in the action bar to see all trades.

**Columns:**
• Date — when the trade was opened
• Pair — which crypto was traded
• Side — BUY or SELL
• Entry — price when trade opened
• Exit — price when trade closed (blank if still open)
• Qty — how many coins were traded
• P&L — profit/loss in USDT ("unrlz" = unrealized, still open)
• Status — Open or Closed
• Strategy — which strategy fired the signal (Donchian / RSI/MACD / Combined / Manual)
• Duration — how long the trade was open
• Reason — the exact signal that triggered the trade

**Filters:**
• Filter by status (Open/Closed)
• Filter by pair (e.g. BTC/USDT)
• Filter by strategy (Donchian / RSI/MACD / Combined)

Use the strategy filter to compare which strategy is performing best for you.`
  },
  {
    id: 'news',
    title: '📰 News and sentiment',
    content: `The bot fetches crypto news every 15 minutes from multiple sources.

**Sources (in priority order):**
1. NewsAPI (requires free key from newsapi.org)
2. CoinDesk RSS feed
3. CryptoPanic RSS feed

**Sentiment scoring:**
Each headline is scored from -1.0 (very bearish) to +1.0 (very bullish).
• With Anthropic key: Claude analyzes headlines in context, checks if news is already priced in
• Without Anthropic key: VADER rule-based sentiment (positive/negative word counting)

The sentiment score per coin (shown as colored bars in the right panel) influences trade decisions:
• Score ≥ 65% = bullish boost (+1 point toward BUY)
• Score ≤ 35% = bearish boost (+1 point toward SELL)
• Score between 35–65% = neutral (no influence)

Click "Refresh news" at any time to fetch the latest headlines immediately.`
  },
  {
    id: 'settings',
    title: '⚙ Settings guide',
    content: `Settings → Strategy tab:
• Strategy mode — which strategy the bot uses
• Max consecutive losses — how many losses before pausing a pair
• Cooldown duration — how long to pause after too many losses

Settings → Risk tab:
• Stop-loss % — max loss per trade (fallback for confluence strategy)
• Take-profit % — target per trade (fallback for confluence strategy)
• Position size — USDT amount per trade
• Max positions — maximum simultaneous open trades
• Demo balance — starting virtual balance for paper trading

Settings → Profit tab:
• Partial close — whether to take early profits at a threshold
• Trailing stop — whether to lock in profits as price moves

Settings → Pairs tab:
• Which pairs the bot monitors and trades
• Any Binance spot USDT pair works (e.g. MATIC/USDT, LINK/USDT)

Settings → API Keys tab:
• Binance API Key & Secret — required for live trading, not needed for demo
• NewsAPI Key — free at newsapi.org, enables better news coverage
• Anthropic API Key — enables Claude AI trade filtering and smart sentiment

Settings → Account tab:
• Change your login password
• Sign out`
  },
  {
    id: 'demo_live',
    title: '🔴 Demo vs Live mode',
    content: `**Demo mode (default)**
• All trades are simulated — no real money involved
• Uses real Binance prices to calculate P&L
• Starting balance is configurable (default $1,000)
• Binance API keys are NOT required
• Safe for testing strategies and learning

**Live mode**
• Executes real orders on your Binance account with real money
• Requires Binance API keys in Settings → API Keys
• A confirmation dialog appears when switching to Live
• "LIVE — REAL FUNDS" warning shown in the topbar

**Switching modes:**
Use the Demo/Live toggle in the topbar. Switching to Live requires confirmation. The bot does not need to be stopped to switch modes.

**Recommendation:**
Run in Demo mode for at least 1–2 weeks before switching to Live. Watch how the signals perform, adjust settings, and only go Live when you are comfortable with the bot's behavior.`
  },
  {
    id: 'prices',
    title: '💹 Real-time prices',
    content: `Prices update in real-time via a direct WebSocket connection to Binance's streaming API. This is the same data feed used by Binance itself — sub-second latency.

The connection streams miniTicker data for all your active pairs simultaneously. Each price tick is pushed to your browser instantly via the backend's SocketIO connection.

The green "Live" dot in the topbar indicates the WebSocket connection to the backend is active. If it shows red, refresh the page — it will reconnect automatically.

Price updates appear in:
• The sidebar (pair list with % change)
• The KPI bar (unrealized P&L updates with price)
• Open positions (live P&L in the right panel)`
  },
  {
    id: 'update',
    title: '🔄 Updating the bot',
    content: `The bot is managed through GitHub + Portainer for easy updates.

**When an update is available:**
1. Download the updated files
2. Replace them in your local tradingbot-repo folder
3. Run: git add . → git commit -m "description" → git push
4. In Portainer → Stacks → tradingbot → Pull and redeploy

**What survives updates:**
• All trade history (stored in Docker volume)
• All settings including API keys (stored in Docker volume)
• Demo balance and open trades

**What resets on update:**
• Nothing important — the database persists in the tradingbot-data Docker volume

**Full rebuild vs redeploy:**
• Python-only changes: just Pull and redeploy
• Frontend (React) changes: Pull and redeploy (Docker rebuilds automatically)
• requirements.txt changes: must do a full remove + redeploy to reinstall packages`
  },
]

export default function HelpPage({ onClose }) {
  const [activeSection, setActiveSection] = useState('overview')
  const [search, setSearch] = useState('')

  const filtered = search
    ? SECTIONS.filter(s => s.title.toLowerCase().includes(search.toLowerCase()) || s.content.toLowerCase().includes(search.toLowerCase()))
    : SECTIONS

  const current = SECTIONS.find(s => s.id === activeSection) || SECTIONS[0]

  return (
    <div style={{position:'fixed',inset:0,background:'var(--bg-base)',zIndex:500,display:'flex',flexDirection:'column'}}>
      {/* Header */}
      <div style={{height:48,background:'var(--bg-surface)',borderBottom:'1px solid var(--border)',display:'flex',alignItems:'center',padding:'0 20px',gap:16,flexShrink:0}}>
        <button onClick={onClose} style={{color:'var(--text-2)',fontSize:18}}>←</button>
        <span style={{fontWeight:600,fontSize:15}}>Help & Documentation</span>
        <span style={{fontSize:12,color:'var(--text-3)'}}>Trading Bot v2.0</span>
      </div>

      <div style={{flex:1,display:'flex',overflow:'hidden',minHeight:0}}>
        {/* Sidebar nav */}
        <div style={{width:240,background:'var(--bg-surface)',borderRight:'1px solid var(--border)',display:'flex',flexDirection:'column',overflow:'hidden',flexShrink:0}}>
          <div style={{padding:'10px 12px',borderBottom:'1px solid var(--border)',flexShrink:0}}>
            <input
              placeholder="Search..."
              value={search}
              onChange={e=>setSearch(e.target.value)}
              style={{fontSize:12}}
            />
          </div>
          <div style={{flex:1,overflowY:'auto',padding:'8px 0'}}>
            {filtered.map(s=>(
              <button key={s.id} onClick={()=>{setActiveSection(s.id);setSearch('')}} style={{
                display:'block',width:'100%',textAlign:'left',padding:'8px 14px',fontSize:12,
                fontWeight:activeSection===s.id?600:400,
                background:activeSection===s.id?'var(--bg-hover)':'transparent',
                color:activeSection===s.id?'var(--text)':'var(--text-2)',
                borderLeft:activeSection===s.id?'2px solid var(--teal)':'2px solid transparent',
              }}>{s.title}</button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div style={{flex:1,overflowY:'auto',padding:'32px 40px',maxWidth:780}}>
          <h1 style={{fontSize:22,fontWeight:600,marginBottom:20,color:'var(--text)'}}>{current.title}</h1>
          <div style={{fontSize:14,lineHeight:1.8,color:'var(--text-2)'}}>
            {current.content.split('\n').map((line,i)=>{
              if (line.startsWith('**') && line.endsWith('**')) {
                return <div key={i} style={{fontWeight:600,color:'var(--text)',marginTop:16,marginBottom:4}}>{line.replace(/\*\*/g,'')}</div>
              }
              if (line.startsWith('• ')) {
                return <div key={i} style={{paddingLeft:16,marginBottom:4,display:'flex',gap:8}}>
                  <span style={{color:'var(--teal)',flexShrink:0}}>•</span>
                  <span dangerouslySetInnerHTML={{__html:line.slice(2).replace(/\*\*(.*?)\*\*/g,'<strong style="color:var(--text)">$1</strong>')}}/>
                </div>
              }
              if (line.trim()==='') return <div key={i} style={{height:8}}/>
              return <p key={i} style={{marginBottom:6}} dangerouslySetInnerHTML={{__html:line.replace(/\*\*(.*?)\*\*/g,'<strong style="color:var(--text)">$1</strong>')}}/>
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
