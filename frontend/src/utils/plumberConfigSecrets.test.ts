import { describe, expect, it } from 'vitest'

import type { PlumberConfig } from '../types/daemon'
import { emptyPlumberConfig } from './plumberConfigDefaults'
import { buildPlumberConfigUpdate, sanitizePlumberConfigResponse } from './plumberConfigSecrets'

describe('Plumber configuration secret contract', () => {
  it('drops legacy API-key readback before configuration enters frontend state', () => {
    const payload = {
      ...emptyPlumberConfig(),
      llm_api_key_configured: true,
      llm_api_key: 'configured-secret',
    } as PlumberConfig

    const sanitized = sanitizePlumberConfigResponse(payload)

    expect(sanitized.llm_api_key_configured).toBe(true)
    expect(sanitized).not.toHaveProperty('llm_api_key')
    expect(JSON.stringify(sanitized)).not.toContain('configured-secret')
  })

  it('omits the API key to preserve the configured value', () => {
    const payload = buildPlumberConfigUpdate(emptyPlumberConfig(), { kind: 'preserve' })

    expect(payload).not.toHaveProperty('llm_api_key')
    expect(payload).not.toHaveProperty('llm_api_key_configured')
  })

  it('sends a replacement only in the write request', () => {
    const payload = buildPlumberConfigUpdate(emptyPlumberConfig(), {
      kind: 'replace',
      value: 'replacement-secret',
    })

    expect(payload.llm_api_key).toBe('replacement-secret')
    expect(payload).not.toHaveProperty('llm_api_key_configured')
  })

  it('uses explicit null to clear the configured key', () => {
    const payload = buildPlumberConfigUpdate(emptyPlumberConfig(), { kind: 'clear' })

    expect(payload.llm_api_key).toBeNull()
    expect(payload).not.toHaveProperty('llm_api_key_configured')
  })
})
