import React, { useState } from 'react'

export default function LoginPage({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)

  const handleSubmit = async () => {
    if (!username || !password) { setError('Enter username and password'); return }
    setLoading(true); setError('')
    try {
      await onLogin(username, password)
    } catch (e) {
      setError(e.response?.data?.error || 'Login failed')
    }
    setLoading(false)
  }

  const handleKey = (e) => { if (e.key === 'Enter') handleSubmit() }

  return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'100vh', background:'var(--bg-base)' }}>
      <div style={{ width:360, padding:32, background:'var(--bg-card)', border:'1px solid var(--border)', borderRadius:'var(--radius-lg)' }}>

        {/* Logo */}
        <div style={{ textAlign:'center', marginBottom:28 }}>
          <div style={{ fontSize:28, marginBottom:8 }}>📈</div>
          <div style={{ fontSize:20, fontWeight:700, color:'var(--text)' }}>Trading Bot</div>
          <div style={{ fontSize:13, color:'var(--text-3)', marginTop:4 }}>Sign in to your dashboard</div>
        </div>

        {/* Form */}
        <div style={{ marginBottom:14 }}>
          <label style={{ fontSize:12, fontWeight:500, display:'block', marginBottom:5 }}>Username</label>
          <input
            type="text"
            value={username}
            onChange={e => setUsername(e.target.value)}
            onKeyDown={handleKey}
            placeholder="admin"
            autoFocus
            style={{ fontSize:14, padding:'10px 12px' }}
          />
        </div>

        <div style={{ marginBottom:20 }}>
          <label style={{ fontSize:12, fontWeight:500, display:'block', marginBottom:5 }}>Password</label>
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            onKeyDown={handleKey}
            placeholder="••••••••"
            style={{ fontSize:14, padding:'10px 12px' }}
          />
        </div>

        {error && (
          <div style={{ background:'var(--red-bg)', border:'1px solid var(--red-dim)', borderRadius:6, padding:'8px 12px', fontSize:12, color:'var(--red)', marginBottom:16 }}>
            {error}
          </div>
        )}

        <button
          onClick={handleSubmit}
          disabled={loading}
          style={{
            width:'100%', padding:'11px', borderRadius:6,
            background: loading ? 'var(--border)' : 'var(--teal)',
            color:'#fff', fontWeight:600, fontSize:14,
            cursor: loading ? 'not-allowed' : 'pointer',
            transition:'background .2s',
          }}
        >
          {loading ? 'Signing in...' : 'Sign in'}
        </button>

        <div style={{ marginTop:16, fontSize:11, color:'var(--text-3)', textAlign:'center' }}>
          Default credentials: admin / admin
        </div>
      </div>
    </div>
  )
}
