import type { PlumberConfig, PlumberConfigUpdate } from '../types/daemon'

export type ApiKeyChange =
  | { kind: 'preserve' }
  | { kind: 'replace'; value: string }
  | { kind: 'clear' }

/** Drop legacy secret readback before a configuration payload reaches React state. */
export function sanitizePlumberConfigResponse(payload: PlumberConfig): PlumberConfig {
  const sanitized = { ...payload } as PlumberConfig & { llm_api_key?: unknown }
  delete sanitized.llm_api_key
  return sanitized
}

/** Build the write contract without echoing response-only key status. */
export function buildPlumberConfigUpdate(
  config: PlumberConfig,
  apiKeyChange: ApiKeyChange,
): PlumberConfigUpdate {
  const update: Partial<PlumberConfig> = { ...sanitizePlumberConfigResponse(config) }
  delete update.llm_api_key_configured
  const payload = update as Omit<PlumberConfig, 'llm_api_key_configured'> & {
    llm_api_key?: string | null
  }
  if (apiKeyChange.kind === 'replace') {
    payload.llm_api_key = apiKeyChange.value
  } else if (apiKeyChange.kind === 'clear') {
    payload.llm_api_key = null
  }
  return payload
}
