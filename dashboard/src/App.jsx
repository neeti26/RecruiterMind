import { useState, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Header from './components/Header'
import InputPanel from './components/InputPanel'
import PipelineProgress from './components/PipelineProgress'
import ResultsDashboard from './components/ResultsDashboard'

const WS_URL = (import.meta.env.VITE_BACKEND_WS_URL || 'ws://localhost:8000') + '/ws/pipeline'

export default function App() {
  const [phase, setPhase] = useState('idle') // idle | running | done | error
  const [pipelineLog, setPipelineLog] = useState([])
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)
  const wsRef = useRef(null)

  const runPipeline = useCallback(({ jdText, candidatesCSV, anonymousMode = false }) => {
    setPhase('running')
    setPipelineLog([])
    setResults(null)
    setError(null)

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      ws.send(JSON.stringify({
        jd_text: jdText,
        candidates_csv: candidatesCSV,
        anonymous_mode: anonymousMode,
      }))
    }

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      if (msg.type === 'log') {
        setPipelineLog(prev => [...prev, msg])
      } else if (msg.type === 'result') {
        setResults(msg.data)
        setPhase('done')
      } else if (msg.type === 'error') {
        setError(msg.message)
        setPhase('error')
      }
    }

    ws.onerror = () => {
      setError('Cannot connect to backend. Make sure the server is running on port 8000.')
      setPhase('error')
    }

    ws.onclose = (e) => {
      // Only treat unexpected close as error (code 1000 = normal close)
      if (e.code !== 1000) {
        setPhase(prev => prev === 'running' ? 'error' : prev)
        setError(prev => prev || 'Connection closed unexpectedly.')
      }
    }
  }, [])

  const reset = useCallback(() => {
    wsRef.current?.close(1000)
    setPhase('idle')
    setPipelineLog([])
    setResults(null)
    setError(null)
  }, [])

  return (
    <div className="min-h-screen bg-[#0f1117]">
      <Header phase={phase} onReset={phase !== 'idle' ? reset : null} />

      <main className="max-w-[1400px] mx-auto px-6 pb-20">
        <AnimatePresence mode="wait">

          {phase === 'idle' && (
            <motion.div key="input"
              initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }} transition={{ duration: 0.25 }}>
              <InputPanel onSubmit={runPipeline} />
            </motion.div>
          )}

          {phase === 'running' && (
            <motion.div key="running"
              initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>
              <PipelineProgress logs={pipelineLog} />
            </motion.div>
          )}

          {phase === 'done' && results && (
            <motion.div key="results"
              initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}>
              <ResultsDashboard results={results} onReset={reset} />
            </motion.div>
          )}

          {phase === 'error' && (
            <motion.div key="error"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className="mt-24 text-center max-w-md mx-auto">
              <div className="w-12 h-12 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center mx-auto mb-4">
                <span className="text-red-400 text-xl">!</span>
              </div>
              <div className="text-white font-semibold mb-2">Pipeline failed</div>
              <div className="text-slate-400 text-sm mb-6 leading-relaxed">{error}</div>
              <button onClick={reset}
                className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 rounded-xl text-white text-sm font-medium transition-colors">
                Try Again
              </button>
            </motion.div>
          )}

        </AnimatePresence>
      </main>
    </div>
  )
}
