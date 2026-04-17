import { useState, useEffect, useRef, useCallback } from 'react'
import { io } from 'socket.io-client'
import axios from 'axios'

const API = '/api'

export function useDashboard() {
  const [data, setData] = useState(null)
  const [connected, setConnected] = useState(false)
  const socketRef = useRef(null)

  useEffect(() => {
    // Fetch immediately — returns fast now with cache
    axios.get(`${API}/dashboard`).then(r => setData(r.data)).catch(console.error)

    const socket = io({ path: '/socket.io', transports: ['websocket', 'polling'] })
    socketRef.current = socket
    socket.on('connect',          () => setConnected(true))
    socket.on('disconnect',       () => setConnected(false))
    socket.on('dashboard_update', d  => setData(d))
    return () => socket.disconnect()
  }, [])

  const post = useCallback(async (url, body = {}) => {
    await axios.post(`${API}${url}`, body)
  }, [])

  const reload = useCallback(() => {
    axios.get(`${API}/dashboard`).then(r => setData(r.data)).catch(console.error)
  }, [])

  return {
    data,
    connected,
    startBot:       () => post('/bot/start'),
    stopBot:        () => post('/bot/stop'),
    setMode:        m  => post('/bot/mode', { mode: m }),
    runNow:         () => post('/bot/run_now'),
    refreshNews:    () => post('/news/refresh'),
    updateSettings: async s => { await post('/settings', s); reload() },
  }
}

export async function fetchOHLCV(symbol, timeframe = '1h', limit = 200) {
  const r = await axios.get(`${API}/ohlcv`, { params: { symbol, timeframe, limit } })
  return r.data
}
