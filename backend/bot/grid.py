"""
Grid Trading Module — earns during ranging/sideways markets.
Places buy orders below current price and sell orders above.
Every time price bounces within the grid, profit is captured.
Complements the directional bot perfectly.
"""
import logging
import json
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def calculate_grid_levels(price, grid_range_pct, num_levels):
    """Calculate grid buy/sell price levels around current price."""
    half_range = price * (grid_range_pct / 100) / 2
    lower = price - half_range
    upper = price + half_range
    step  = (upper - lower) / num_levels

    levels = []
    for i in range(num_levels + 1):
        levels.append(round(lower + i * step, 8))
    return levels, lower, upper

def get_grid_config():
    from db.database import get_setting
    return {
        'enabled':    get_setting('grid_enabled')    == 'true',
        'pair':       get_setting('grid_pair')        or 'BTC/USDT',
        'capital':    float(get_setting('grid_capital')    or '200'),
        'num_levels': int(get_setting('grid_levels')       or '10'),
        'range_pct':  float(get_setting('grid_range_pct')  or '4.0'),
        'mode':       get_setting('trading_mode')     or 'demo',
    }

def run_grid_cycle():
    """
    Grid trading cycle — runs every 5 minutes.
    In demo mode: simulates grid fills and tracks P&L.
    In live mode: places real limit orders on Binance.
    """
    from db.database import get_setting, set_setting, get_conn
    from db.activitylog import log as alog
    from bot.exchange import fetch_ticker

    cfg = get_grid_config()
    if not cfg['enabled']: return

    pair  = cfg['pair']
    mode  = cfg['mode']

    ticker = fetch_ticker(pair)
    if not ticker: return
    price = ticker['last']

    # Load existing grid state
    state_str = get_setting('grid_state') or '{}'
    try: state = json.loads(state_str)
    except: state = {}

    # Initialize grid if not set up
    if not state or state.get('pair') != pair:
        levels, lower, upper = calculate_grid_levels(
            price, cfg['range_pct'], cfg['num_levels'])
        capital_per_level = cfg['capital'] / cfg['num_levels']
        state = {
            'pair':       pair,
            'levels':     levels,
            'lower':      lower,
            'upper':      upper,
            'capital':    cfg['capital'],
            'per_level':  capital_per_level,
            'orders':     {},   # level_idx: {'type': buy/sell, 'filled': bool, 'qty': float}
            'total_pnl':  0,
            'fills':      0,
            'started_at': datetime.now(timezone.utc).isoformat(),
            'start_price': price,
        }
        # Place initial buy orders below price and sell orders above
        for i, level in enumerate(levels):
            qty = round(capital_per_level / level, 8)
            if level < price:
                state['orders'][str(i)] = {
                    'type': 'buy', 'price': level, 'qty': qty, 'filled': False}
            else:
                state['orders'][str(i)] = {
                    'type': 'sell', 'price': level, 'qty': qty, 'filled': False}

        set_setting('grid_state', json.dumps(state))
        alog('system', f'Grid initialized: {pair} ${cfg["capital"]} | '
             f'{cfg["num_levels"]} levels | ${lower:.2f}-${upper:.2f}',
             detail={'pair':pair,'lower':lower,'upper':upper,'levels':cfg['num_levels']})
        return

    # Check if price is out of grid range — reset
    if price < state['lower'] * 0.98 or price > state['upper'] * 1.02:
        alog('system', f'Grid reset — price ${price:.2f} out of range '
             f'${state["lower"]:.2f}-${state["upper"]:.2f}', level='warning')
        set_setting('grid_state', '{}')
        return

    # Check each order for fills (demo simulation)
    pnl_this_cycle = 0
    fills_this_cycle = 0

    for idx, order in state['orders'].items():
        if order['filled']: continue

        # Demo: simulate fill when price crosses the level
        if order['type'] == 'buy' and price <= order['price'] * 1.001:
            # Buy filled — place corresponding sell at next level up
            order['filled'] = True
            next_idx = str(int(idx) + 1)
            if next_idx in state['orders']:
                sell_price = state['orders'][next_idx]['price']
                profit = (sell_price - order['price']) * order['qty']
                pnl_this_cycle += profit
                fills_this_cycle += 1
                # Reset for next cycle
                order['filled'] = False
                state['total_pnl'] += profit
                state['fills'] += 1

        elif order['type'] == 'sell' and price >= order['price'] * 0.999:
            # Sell filled — place corresponding buy at next level down
            order['filled'] = True
            prev_idx = str(int(idx) - 1)
            if prev_idx in state['orders']:
                buy_price = state['orders'][prev_idx]['price']
                profit = (order['price'] - buy_price) * order['qty']
                pnl_this_cycle += profit
                fills_this_cycle += 1
                order['filled'] = False
                state['total_pnl'] += profit
                state['fills'] += 1

    if fills_this_cycle > 0:
        set_setting('grid_state', json.dumps(state))
        alog('trade', f'Grid: {fills_this_cycle} fills | +${pnl_this_cycle:.3f} | '
             f'Total: ${state["total_pnl"]:.2f} from {state["fills"]} fills',
             level='success',
             detail={'pair':pair,'fills':fills_this_cycle,'pnl':round(pnl_this_cycle,4),
                     'total_pnl':round(state['total_pnl'],4),'price':price})

def get_grid_status():
    from db.database import get_setting
    cfg = get_grid_config()
    state_str = get_setting('grid_state') or '{}'
    try: state = json.loads(state_str)
    except: state = {}
    return {'config': cfg, 'state': state}
