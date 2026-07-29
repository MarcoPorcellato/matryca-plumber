/** Frontend coercion tests for shadow_db on /api/state (#185). */

import { describe, expect, it } from 'vitest'

import { DEFAULT_SHADOW_DB_STATE, normalizeDaemonState } from '../types/daemon'

const BASE_STATE = {
  version: 1,
  files: {},
  status: 'idle' as const,
  model: 'test',
  bootstrap_complete: false,
  bootstrap_scanned: 0,
  bootstrap_total: 0,
  session_prompt_tokens: 0,
  session_completion_tokens: 0,
  current_cluster: null,
  current_cluster_files_total: 0,
  current_cluster_files_done: 0,
  phase2_llm_turns: 0,
  last_scan_at: null,
  last_file: null,
}

describe('normalizeDaemonState shadow_db', () => {
  it('defaults when shadow_db is missing', () => {
    const normalized = normalizeDaemonState(BASE_STATE)
    expect(normalized.shadow_db).toEqual(DEFAULT_SHADOW_DB_STATE)
  })

  it.each([
    ['disabled', { enabled: false, state: 'disabled' }],
    ['bootstrapping', { enabled: true, state: 'bootstrapping' }],
    ['ready', { enabled: true, state: 'ready' }],
    ['stale', { enabled: true, state: 'stale' }],
    ['error', { enabled: true, state: 'error', last_sync_error: 'sync failed' }],
  ] as const)('preserves %s state', (_label, shadowDb) => {
    const normalized = normalizeDaemonState({
      ...BASE_STATE,
      shadow_db: {
        last_full_sync_at: null,
        source_page_count: null,
        indexed_page_count: null,
        lag_pages: null,
        last_sync_error: null,
        not_ready_reason: null,
        quarantined_page_count: 0,
        ...shadowDb,
      },
    })
    expect(normalized.shadow_db?.state).toBe(shadowDb.state)
    expect(normalized.shadow_db?.enabled).toBe(shadowDb.enabled)
    if ('last_sync_error' in shadowDb) {
      expect(normalized.shadow_db?.last_sync_error).toBe(shadowDb.last_sync_error)
    }
  })

  it('coerces camelCase shadowDb payload', () => {
    const normalized = normalizeDaemonState({
      ...BASE_STATE,
      shadowDb: {
        enabled: true,
        state: 'ready',
        lastFullSyncAt: '2026-07-18T10:00:00+00:00',
        sourcePageCount: 5,
        indexedPageCount: 3,
        lagPages: 2,
        lastSyncError: null,
      },
    } as never)
    expect(normalized.shadow_db).toEqual({
      enabled: true,
      state: 'ready',
      last_full_sync_at: '2026-07-18T10:00:00+00:00',
      source_page_count: 5,
      indexed_page_count: 3,
      lag_pages: 2,
      last_sync_error: null,
      not_ready_reason: null,
      quarantined_page_count: 0,
    })
  })

  it('surfaces the not-ready reason so the operator sees why reads are not accelerated', () => {
    const normalized = normalizeDaemonState({
      ...BASE_STATE,
      shadow_db: {
        enabled: true,
        state: 'stale',
        not_ready_reason: 'full_sync_incomplete',
      },
    } as never)
    expect(normalized.shadow_db?.not_ready_reason).toBe('full_sync_incomplete')
  })

  it('drops an unknown reason code rather than rendering it raw', () => {
    const normalized = normalizeDaemonState({
      ...BASE_STATE,
      shadow_db: { enabled: true, state: 'stale', not_ready_reason: 'something_new' },
    } as never)
    expect(normalized.shadow_db?.not_ready_reason).toBeNull()
  })

  it('clears the reason once the cache is ready', () => {
    const normalized = normalizeDaemonState({
      ...BASE_STATE,
      shadow_db: { enabled: true, state: 'ready', not_ready_reason: 'sync_error' },
    } as never)
    expect(normalized.shadow_db?.not_ready_reason).toBeNull()
  })

  it('surfaces the parked page count alongside a ready cache', () => {
    const normalized = normalizeDaemonState({
      ...BASE_STATE,
      shadow_db: { enabled: true, state: 'ready', quarantined_page_count: 25 },
    } as never)
    expect(normalized.shadow_db?.quarantined_page_count).toBe(25)
  })

  it('defaults the parked page count to zero on daemons that omit it', () => {
    const normalized = normalizeDaemonState({
      ...BASE_STATE,
      shadow_db: { enabled: true, state: 'ready' },
    } as never)
    expect(normalized.shadow_db?.quarantined_page_count).toBe(0)
  })

  it('forces disabled state when enabled is false', () => {
    const normalized = normalizeDaemonState({
      ...BASE_STATE,
      shadow_db: {
        enabled: false,
        state: 'ready',
        last_full_sync_at: null,
        source_page_count: null,
        indexed_page_count: null,
        lag_pages: null,
        last_sync_error: null,
        not_ready_reason: null,
        quarantined_page_count: 0,
      },
    })
    expect(normalized.shadow_db?.state).toBe('disabled')
  })
})
