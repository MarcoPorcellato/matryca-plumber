import { useCallback, useEffect, useRef, useState } from 'react'

import type {
  ConnectionStatus,
  DaemonControlResponse,
  DaemonStateResponse,
  GraphAnalytics,
  PlumberConfig,
  PlumberConfigUpdate,
  PlumberPollSnapshot,
} from '../types/daemon'
import { normalizeDaemonState, normalizeGraphAnalytics } from '../types/daemon'
import {
  MATRYCA_API_BASE,
  MATRYCA_GRAPH_ANALYTICS_TIMEOUT_MS,
  matrycaFetchJson,
} from '../utils/matrycaApiAuth'
import { sanitizePlumberConfigResponse } from '../utils/plumberConfigSecrets'

/** Base interval between telemetry poll cycles (distributed requests within each cycle). */
const POLL_CYCLE_MS = 5000
/** Delay between sequential API calls inside one cycle to avoid request bursts. */
const POLL_STAGGER_MS = 1200
/** Fetch graph analytics every N cycles (~20s at 5s/cycle). */
const GRAPH_ANALYTICS_EVERY_N_CYCLES = 4

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

/** Treat daemon start responses that should enable live UI polling. */
function isStartAccepted(result: DaemonControlResponse): boolean {
  return result.ok || result.code === 'already_running'
}

export function usePlumberPolling(cycleMs = POLL_CYCLE_MS): PlumberPollSnapshot {
  const [state, setState] = useState<DaemonStateResponse | null>(null)
  const [logs, setLogs] = useState<string[]>([])
  const [config, setConfig] = useState<PlumberConfig | null>(null)
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('connecting')
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null)
  const [frozen, setFrozen] = useState(true)
  const [engineBusy, setEngineBusy] = useState(false)
  const [engineError, setEngineError] = useState<string | null>(null)

  const stateRef = useRef<DaemonStateResponse | null>(null)
  const graphAnalyticsRef = useRef<GraphAnalytics | undefined>(undefined)
  const logsRef = useRef<string[]>([])
  const mountedRef = useRef(true)
  const cycleTimeoutRef = useRef<number | null>(null)
  const cycleGenerationRef = useRef(0)
  const pollCycleCountRef = useRef(0)
  const frozenRef = useRef(true)
  /** True after the operator clicks Start — keeps polling even while status is still ``stopped``. */
  const telemetryLiveRef = useRef(false)

  const clearCycleTimer = useCallback(() => {
    if (cycleTimeoutRef.current !== null) {
      window.clearTimeout(cycleTimeoutRef.current)
      cycleTimeoutRef.current = null
    }
  }, [])

  const setTelemetryLive = useCallback(
    (live: boolean) => {
      telemetryLiveRef.current = live
      frozenRef.current = !live
      setFrozen(!live)
      if (!live) {
        clearCycleTimer()
        cycleGenerationRef.current += 1
      }
    },
    [clearCycleTimer],
  )

  const applyConnectionFromPoll = useCallback((stateOk: boolean, logsOk: boolean) => {
    if (!mountedRef.current) return
    if (stateOk || logsOk) {
      setConnectionStatus('live')
      setLastUpdatedAt(new Date())
    } else if (!stateRef.current) {
      setConnectionStatus('offline')
    } else {
      setConnectionStatus('connecting')
    }
  }, [])

  const pollState = useCallback(async (): Promise<boolean> => {
    try {
      const rawState = await matrycaFetchJson<DaemonStateResponse>(
        `${MATRYCA_API_BASE}/api/state`,
      )
      const nextState = normalizeDaemonState({
        ...rawState,
        graph_analytics: graphAnalyticsRef.current,
      })
      if (!mountedRef.current) return false
      stateRef.current = nextState
      setState(nextState)
      setConnectionError(null)

      const daemonAlive =
        nextState.daemon_pid != null && nextState.daemon_pid > 0
      if (
        frozenRef.current
        && !telemetryLiveRef.current
        && (nextState.status === 'running' || nextState.status === 'idle' || daemonAlive)
      ) {
        telemetryLiveRef.current = true
        frozenRef.current = false
        setFrozen(false)
      }
      return true
    } catch (error) {
      if (!mountedRef.current) return false
      console.warn('[Matryca Plumber] poll: /api/state failed', error)
      setConnectionError(error instanceof Error ? error.message : 'state request failed')
      return false
    }
  }, [])

  const pollGraphAnalytics = useCallback(async (): Promise<boolean> => {
    try {
      const graphAnalytics = normalizeGraphAnalytics(
        await matrycaFetchJson<GraphAnalytics>(
          `${MATRYCA_API_BASE}/api/graph-analytics`,
          undefined,
          { timeoutMs: MATRYCA_GRAPH_ANALYTICS_TIMEOUT_MS },
        ),
      )
      if (!mountedRef.current) return false
      graphAnalyticsRef.current = graphAnalytics
      if (stateRef.current) {
        const merged = normalizeDaemonState({
          ...stateRef.current,
          graph_analytics: graphAnalytics,
        })
        stateRef.current = merged
        setState(merged)
      }
      setConnectionError(null)
      return true
    } catch (error) {
      if (!mountedRef.current) return false
      const message = error instanceof Error ? error.message : 'graph analytics request failed'
      console.warn('[Matryca Plumber] poll: /api/graph-analytics failed', message)
      if (stateRef.current) {
        const offline = normalizeGraphAnalytics({ status: 'offline' })
        const merged = normalizeDaemonState({
          ...stateRef.current,
          graph_analytics: offline,
        })
        stateRef.current = merged
        setState(merged)
      }
      return false
    }
  }, [])

  const pollLogs = useCallback(async (): Promise<boolean> => {
    try {
      const nextLogs = await matrycaFetchJson<string[]>(`${MATRYCA_API_BASE}/api/logs`)
      if (!mountedRef.current) return false
      const cleaned = nextLogs.filter((line) => line.trim().length > 0)
      logsRef.current = cleaned
      setLogs(cleaned)
      setConnectionError(null)
      return true
    } catch (error) {
      if (!mountedRef.current) return false
      console.warn('[Matryca Plumber] poll: /api/logs failed', error)
      setConnectionError(error instanceof Error ? error.message : 'logs request failed')
      return false
    }
  }, [])

  /** One-shot state fetch when telemetry is frozen (no logs/analytics). */
  const pollFrozenSnapshot = useCallback(async () => {
    const stateOk = await pollState()
    applyConnectionFromPoll(stateOk, false)
  }, [applyConnectionFromPoll, pollState])

  /** Immediate full refresh (Start/Stop/mount). */
  const pollFull = useCallback(async () => {
    const stateOk = await pollState()
    let logsOk = false
    let analyticsOk = false

    if (!frozenRef.current) {
      await pollGraphAnalytics().then((ok) => {
        analyticsOk = ok
      })
      logsOk = await pollLogs()
    }

    applyConnectionFromPoll(stateOk, logsOk || analyticsOk)
  }, [applyConnectionFromPoll, pollGraphAnalytics, pollLogs, pollState])

  const runTelemetryCycleRef = useRef<(generation: number) => Promise<void>>(async () => {})

  const runTelemetryCycle = useCallback(
    async (generation: number) => {
      if (!mountedRef.current || generation !== cycleGenerationRef.current) return
      if (frozenRef.current) return

      const cycleStartedAt = Date.now()
      pollCycleCountRef.current += 1
      const cycleIndex = pollCycleCountRef.current
      const fetchAnalytics = cycleIndex % GRAPH_ANALYTICS_EVERY_N_CYCLES === 0

      const stateOk = await pollState()
      if (!mountedRef.current || generation !== cycleGenerationRef.current) return

      await sleep(POLL_STAGGER_MS)
      if (!mountedRef.current || generation !== cycleGenerationRef.current) return

      const logsOk = await pollLogs()
      if (!mountedRef.current || generation !== cycleGenerationRef.current) return

      let analyticsOk = false
      if (fetchAnalytics) {
        await sleep(POLL_STAGGER_MS)
        if (!mountedRef.current || generation !== cycleGenerationRef.current) return
        analyticsOk = await pollGraphAnalytics()
      }

      applyConnectionFromPoll(stateOk, logsOk || analyticsOk)

      if (!mountedRef.current || generation !== cycleGenerationRef.current) return
      const elapsed = Date.now() - cycleStartedAt
      const delay = Math.max(0, cycleMs - elapsed)
      cycleTimeoutRef.current = window.setTimeout(() => {
        void runTelemetryCycleRef.current(generation)
      }, delay)
    },
    [applyConnectionFromPoll, cycleMs, pollGraphAnalytics, pollLogs, pollState],
  )

  useEffect(() => {
    runTelemetryCycleRef.current = runTelemetryCycle
  }, [runTelemetryCycle])

  const startTelemetryLoop = useCallback(() => {
    clearCycleTimer()
    const generation = cycleGenerationRef.current
    void runTelemetryCycle(generation)
  }, [clearCycleTimer, runTelemetryCycle])

  useEffect(() => {
    mountedRef.current = true
    queueMicrotask(() => {
      void pollFrozenSnapshot()
    })
    return () => {
      mountedRef.current = false
      cycleGenerationRef.current += 1
      clearCycleTimer()
    }
  }, [clearCycleTimer, pollFrozenSnapshot])

  useEffect(() => {
    if (frozen) {
      clearCycleTimer()
      cycleGenerationRef.current += 1
      return
    }
    pollCycleCountRef.current = 0
    void pollFull()
    startTelemetryLoop()
    return () => {
      cycleGenerationRef.current += 1
      clearCycleTimer()
    }
  }, [clearCycleTimer, frozen, pollFull, startTelemetryLoop])

  /** While UI is frozen, still poll checkpoint state when a live daemon PID is reported. */
  useEffect(() => {
    if (!frozen) {
      return
    }
    const pid = state?.daemon_pid
    if (pid == null || pid <= 0) {
      return
    }
    const intervalId = window.setInterval(() => {
      void pollState()
    }, cycleMs)
    return () => {
      window.clearInterval(intervalId)
    }
  }, [cycleMs, frozen, pollState, state?.daemon_pid])

  const refreshConfig = useCallback(async () => {
    try {
      const payload = sanitizePlumberConfigResponse(
        await matrycaFetchJson<PlumberConfig>(`${MATRYCA_API_BASE}/api/config`),
      )
      if (mountedRef.current) {
        setConfig(payload)
        setConnectionError(null)
      }
      return payload
    } catch (error) {
      console.warn('[Matryca Plumber] refreshConfig: /api/config failed', error)
      if (mountedRef.current) {
        setConfig(null)
        setConnectionError(error instanceof Error ? error.message : 'config request failed')
      }
      return null
    }
  }, [])

  const applyConfig = useCallback((payload: PlumberConfig) => {
    if (mountedRef.current) {
      setConfig(sanitizePlumberConfigResponse(payload))
      setConnectionError(null)
    }
  }, [])

  useEffect(() => {
    queueMicrotask(() => {
      void refreshConfig()
    })
  }, [refreshConfig])

  const startEngine = useCallback(async () => {
    setEngineBusy(true)
    setEngineError(null)
    try {
      const result = await matrycaFetchJson<DaemonControlResponse>(`${MATRYCA_API_BASE}/api/daemon/start`, {
        method: 'POST',
      })
      if (!isStartAccepted(result)) {
        setEngineError(result.message ?? 'Failed to start engine')
        return
      }
      setTelemetryLive(true)
      await pollFull()
    } catch (error) {
      if (mountedRef.current) {
        setEngineError(error instanceof Error ? error.message : 'Failed to start engine')
      }
    } finally {
      if (mountedRef.current) {
        setEngineBusy(false)
      }
    }
  }, [pollFull, setTelemetryLive])

  const stopEngine = useCallback(async () => {
    setEngineBusy(true)
    setEngineError(null)
    try {
      const result = await matrycaFetchJson<DaemonControlResponse>(`${MATRYCA_API_BASE}/api/daemon/stop`, {
        method: 'POST',
      })
      if (!result.ok) {
        setEngineError(result.message ?? 'Failed to stop engine')
        return
      }
      setTelemetryLive(false)
      await pollFrozenSnapshot()
    } catch (error) {
      if (mountedRef.current) {
        setEngineError(error instanceof Error ? error.message : 'Failed to stop engine')
      }
    } finally {
      if (mountedRef.current) {
        setEngineBusy(false)
      }
    }
  }, [pollFrozenSnapshot, setTelemetryLive])

  const saveConfig = useCallback(async (payload: PlumberConfigUpdate): Promise<PlumberConfig | null> => {
    try {
      const updated = sanitizePlumberConfigResponse(
        await matrycaFetchJson<PlumberConfig>(`${MATRYCA_API_BASE}/api/config`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        }),
      )
      if (mountedRef.current) {
        setConfig(updated)
      }
      return updated
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to save config'
      throw error instanceof Error ? error : new Error(message)
    }
  }, [])

  return {
    state,
    logs,
    config,
    connectionStatus,
    connectionError,
    lastUpdatedAt,
    frozen,
    engineBusy,
    engineError,
    startEngine,
    stopEngine,
    saveConfig,
    refreshConfig,
    applyConfig,
  }
}
