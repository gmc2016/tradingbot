import { useState, useEffect, useRef, useCallback } from 'react'
import { io } from 'socket.io-client'
import axios from 'axios'

const API = '/api'
axios.defaults.withCredentials = true

export function useAuth() {
  const [auth, setAuth] = useState(null) // null=loading, false=logged out, {username}=logged in

  useEffect(() => {
    axios.get(`${API}/auth/status`)
      .then(r => setAuth(r.data.logged_in ? r.data : false))
      .catch(() => setAuth(false))
  }, [])

  const login = useCallback(async (username, password) => {
    const r = await axios.post(`${API}/auth/login`, { username, password })
    setAuth(r.data)
    return r.data
  }, [])

  const logout = useCallback(async () => {
    await axios.post(`${API}/auth/logout`)
    setAuth(false)
  }, [])

  const changePassword = useCallback(async (newPassword) => {
    await axios.post(`${API}/auth/change_password`, { new_password: newPassword })
  }, [])

  return { auth, login, logout, changePassword }
}

export function useDashboard() {
  const [data,      setData]      = useState(null)
  const [connected, setConnected] = useState(false)
  const [prices,    setPrices]    = useState({})
  const socketRef = useRef(null)

  useEffect(() => {
    axios.get(`${API}/dashboard`).then(r => setData(r.data)).catch(e => {
      if (e.response?.status === 401) setData({ __unauthorized: true })
    })
    const socket = io({ path: '/socket.io', transports: ['websocket', 'polling'] })
    socketRef.current = socket
    socket.on('connect',          () => setConnected(true))
    socket.on('disconnect',       () => setConnected(false))
    socket.on('dashboard_update', d  => setData(d))
    socket.on('price_update', ({ pair, price, change }) => {
      setPrices(prev => ({ ...prev, [pair]: { price, change } }))
    })
    return () => socket.disconnect()
  }, [])

  const post = useCallback(async (url, body = {}) => {
    return await axios.post(`${API}${url}`, body)
  }, [])

  const reload = useCallback(() => {
    axios.get(`${API}/dashboard`).then(r => setData(r.data)).catch(console.error)
  }, [])

  return {
    data, connected, prices,
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
