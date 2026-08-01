import { useCallback, useEffect, useRef, useState } from 'react'

import type { LmModelsResponse, PlumberConfig } from '../types/daemon'
import { MATRYCA_API_BASE, matrycaAuthenticatedFetch } from '../utils/matrycaApiAuth'
import { emptyPlumberConfig } from '../utils/plumberConfigDefaults'

interface SettingsDrawerProps {
  open: boolean
  config: PlumberConfig | null
  onClose: () => void
  onSave: (payload: PlumberConfig) => Promise<PlumberConfig | null>
}

interface FieldSpec {
  key: keyof PlumberConfig
  label: string
  description: string
  type: 'text' | 'password' | 'number' | 'boolean' | 'lm-model'
  step?: string
  badge?: string
  badgeClass?: string
  writesGraph?: boolean
}

interface TrustSection {
  id: string
  title: string
  subtitle: string
  borderClass: string
  badgeClass: string
  fields: FieldSpec[]
}

const INPUT_CLASS =
  'w-full rounded-xl border border-theme-border/50 bg-theme-base px-3 py-2 text-sm text-theme-text outline-none transition placeholder:text-theme-muted focus:border-theme-accent/60 focus:ring-2 focus:ring-theme-accent/30'

const RUNTIME_POLICY_FIELDS: FieldSpec[] = [
  {
    key: 'read_only',
    label: 'Strict Read Only',
    description:
      'Blocks every Matryca write inside the Logseq graph. Read tools and the external Shadow cache remain available.',
    type: 'boolean',
    badge: 'Vault protected',
    badgeClass: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-500',
  },
  {
    key: 'shadow_db_enabled',
    label: 'Shadow DB Acceleration',
    description:
      'Maintains a derived SQLite read cache outside the graph. Disable it to force Markdown/BM25 reads.',
    type: 'boolean',
    badge: 'External cache',
    badgeClass: 'border-blue-500/40 bg-blue-500/10 text-blue-500',
  },
]

const INFRA_FIELDS: FieldSpec[] = [
  {
    key: 'logseq_graph_path',
    label: 'Logseq Graph Path',
    description: 'Root folder of your local Logseq OG markdown vault.',
    type: 'text',
  },
  {
    key: 'lm_studio_url',
    label: 'LLM Base URL',
    description:
      'OpenAI-compatible endpoint: LOCAL (LM Studio: :1234/v1, Ollama: :11434/v1) or CLOUD.',
    type: 'text',
  },
  {
    key: 'lm_model',
    label: 'LLM Model',
    description: 'Exact model id from your provider (Ollama requires the precise tag, e.g. llama3:8b).',
    type: 'lm-model',
  },
  {
    key: 'llm_api_key',
    label: 'API Token',
    description:
      'Bearer token sent as Authorization on cloud OpenAI-compatible endpoints. Required only for CLOUD; local LM Studio / Ollama may use dummy-key.',
    type: 'password',
  },
  {
    key: 'thermal_delay_bootstrap',
    label: 'Bootstrap Thermal Delay (s)',
    description: 'Cool-down after catalog/bootstrap LLM calls.',
    type: 'number',
    step: '0.1',
  },
  {
    key: 'thermal_delay_cognitive',
    label: 'Cognitive Thermal Delay (s)',
    description: 'Cool-down after Phase-2 lint and enrichment inferences.',
    type: 'number',
    step: '0.1',
  },
  {
    key: 'mapreduce_trigger_chars',
    label: 'MapReduce Trigger (chars)',
    description: 'Giant pages above this size are chunked before LLM harvest.',
    type: 'number',
    step: '1000',
  },
  {
    key: 'mapreduce_chunk_chars',
    label: 'MapReduce Chunk (chars)',
    description: 'Maximum characters per MapReduce summarization chunk.',
    type: 'number',
    step: '1000',
  },
  {
    key: 'compression_trigger',
    label: 'Compression Trigger (tokens)',
    description: 'Rolling LLM history condenses once estimated tokens exceed this threshold.',
    type: 'number',
    step: '1000',
  },
  {
    key: 'compression_target',
    label: 'Compression Target (tokens)',
    description: 'Target token budget after context condensation completes.',
    type: 'number',
    step: '1000',
  },
  {
    key: 'low_priority_mode',
    label: 'Hardware Guard (Low Priority)',
    description: 'POSIX niceness 19 — Plumber yields CPU to foreground work.',
    type: 'boolean',
  },
]

const TRUST_SECTIONS: TrustSection[] = [
  {
    id: 'safe',
    title: 'Safe Mode',
    subtitle: 'Reads context and adds metadata only. Recommended default.',
    borderClass: 'border-emerald-500/30',
    badgeClass: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-500',
    fields: [
      {
        key: 'semantic_routing',
        label: 'Semantic Routing',
        description: 'Cache LLM index results by page fingerprint (read-only on disk).',
        type: 'boolean',
        badge: '🛡️ Safe',
        badgeClass: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-500',
      },
      {
        key: 'context_compression',
        label: 'Context Compression',
        description: 'Rolling condensation of multi-turn LLM history in memory only.',
        type: 'boolean',
        badge: '🛡️ Safe',
        badgeClass: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-500',
      },
      {
        key: 'entity_consolidation',
        label: 'Entity Consolidation',
        description: 'Adds alias:: lines on canonical pages when duplicates are detected.',
        type: 'boolean',
        badge: '📝 Metadata',
        badgeClass: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-500',
        writesGraph: true,
      },
      {
        key: 'property_hygiene',
        label: 'Property Hygiene',
        description: 'Infers missing key:: value properties from page tags.',
        type: 'boolean',
        badge: '📝 Metadata',
        badgeClass: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-500',
        writesGraph: true,
      },
      {
        key: 'marpa_framework',
        label: 'MARPA Framework',
        description: 'Assigns type:: domain metadata and validation side-sections.',
        type: 'boolean',
        badge: '📝 Metadata',
        badgeClass: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-500',
        writesGraph: true,
      },
    ],
  },
  {
    id: 'augmented',
    title: 'Augmented Mode',
    subtitle: 'Adds content in isolated side-blocks or new pages — your bullets stay intact.',
    borderClass: 'border-amber-500/30',
    badgeClass: 'border-amber-500/40 bg-amber-500/10 text-amber-500',
    fields: [
      {
        key: 'heal_dangling',
        label: 'Heal Dangling Links',
        description: 'Creates isolated seed pages for broken [[WikiLinks]] — never edits your text.',
        type: 'boolean',
        badge: '📎 Side blocks',
        badgeClass: 'border-amber-500/40 bg-amber-500/10 text-amber-500',
        writesGraph: true,
      },
      {
        key: 'backpropagate_links',
        label: 'Backpropagate Links',
        description: 'Appends ### Matryca Backlink Context sections on target pages.',
        type: 'boolean',
        badge: '📎 Side blocks',
        badgeClass: 'border-amber-500/40 bg-amber-500/10 text-amber-500',
        writesGraph: true,
      },
    ],
  },
  {
    id: 'surgeon',
    title: 'Surgeon Mode',
    subtitle: 'Alters your original bullet text or block structure. Handle with care.',
    borderClass: 'border-red-500/40',
    badgeClass: 'border-red-500/40 bg-red-500/10 text-red-500',
    fields: [
      {
        key: 'enable_inline_semantic_corrections',
        label: 'Enable Inline Semantic Corrections',
        description:
          'Wraps concepts in [[WikiLinks]] inside your bullets. Stamps matryca-plumber:: true for audit.',
        type: 'boolean',
        badge: '⚠️ Modifies text',
        badgeClass: 'border-red-500/40 bg-red-500/10 text-red-500',
        writesGraph: true,
      },
      {
        key: 'auto_split',
        label: 'Auto-Split Dense Blocks',
        description: 'Extracts oversized subtrees into new pages and replaces them with link stubs.',
        type: 'boolean',
        badge: '💣 Structural',
        badgeClass: 'border-red-500/50 bg-red-500/10 text-red-500',
        writesGraph: true,
      },
    ],
  },
]

const NUMERIC_FIELDS = new Set<keyof PlumberConfig>([
  'thermal_delay_bootstrap',
  'thermal_delay_cognitive',
  'mapreduce_trigger_chars',
  'mapreduce_chunk_chars',
  'compression_trigger',
  'compression_target',
])

function parseNumericField(raw: string): number | null {
  const trimmed = raw.trim()
  if (!trimmed) {
    return null
  }
  const parsed = Number(trimmed)
  if (Number.isNaN(parsed) || !Number.isFinite(parsed)) {
    return null
  }
  return parsed
}

function RiskBadge({ label, className }: { label: string; className: string }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded border px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wider ${className}`}
    >
      {label}
    </span>
  )
}

function LmModelField({
  open,
  field,
  lmStudioUrl,
  value,
  onChange,
}: {
  open: boolean
  field: FieldSpec
  lmStudioUrl: string
  value: string
  onChange: (model: string) => void
}) {
  const [models, setModels] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const loadModels = useCallback(async () => {
    const trimmedUrl = lmStudioUrl.trim()
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    if (!trimmedUrl) {
      setModels([])
      setError('LM Studio URL is required')
      return
    }

    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({ base_url: trimmedUrl })
      const response = await matrycaAuthenticatedFetch(
        `${MATRYCA_API_BASE}/api/lm-models?${params.toString()}`,
        {
          headers: { Accept: 'application/json' },
          signal: controller.signal,
        },
      )
      if (controller.signal.aborted) {
        return
      }
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      const payload = (await response.json()) as LmModelsResponse
      if (controller.signal.aborted) {
        return
      }
      if (payload.error) {
        setError(payload.error)
        setModels([])
        return
      }
      setModels(payload.models)
    } catch (fetchError) {
      if (controller.signal.aborted) {
        return
      }
      setError(fetchError instanceof Error ? fetchError.message : 'Failed to load models')
      setModels([])
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false)
      }
    }
  }, [lmStudioUrl])

  useEffect(() => {
    if (!open) {
      abortRef.current?.abort()
      return
    }
    const timer = window.setTimeout(() => {
      void loadModels()
    }, 300)
    return () => {
      window.clearTimeout(timer)
      abortRef.current?.abort()
    }
  }, [open, loadModels])

  const options = models.includes(value) || !value ? models : [value, ...models]
  const useSelect = !error && options.length > 0

  return (
    <label className="block space-y-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-theme-text">{field.label}</span>
      </div>
      <p className="text-[11px] leading-relaxed text-theme-muted">{field.description}</p>
      <div className="flex items-center gap-2">
        {useSelect ? (
          <select
            value={value}
            onChange={(event) => onChange(event.target.value)}
            className={`${INPUT_CLASS} flex-1`}
          >
            {options.map((modelId) => (
              <option key={modelId} value={modelId}>
                {modelId}
              </option>
            ))}
          </select>
        ) : (
          <input
            type="text"
            value={value}
            onChange={(event) => onChange(event.target.value)}
            placeholder={loading ? 'Loading models…' : 'Model id'}
            className={`${INPUT_CLASS} flex-1`}
          />
        )}
        <button
          type="button"
          onClick={() => void loadModels()}
          disabled={loading}
          aria-label="Refresh model list"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-theme-border/50 bg-theme-base text-xs text-theme-muted transition hover:text-theme-text disabled:opacity-50"
        >
          {loading ? '…' : '↻'}
        </button>
      </div>
      {error ? (
        <p className="text-[10px] text-amber-500">
          Could not reach LM Studio ({error}). Enter the model id manually.
        </p>
      ) : null}
      {!error && !loading && open && models.length === 0 ? (
        <p className="text-[10px] text-theme-muted">
          No loaded models found — load one in LM Studio, then refresh.
        </p>
      ) : null}
    </label>
  )
}

function ConfigField({
  field,
  draft,
  invalidFields,
  disabled = false,
  onChange,
}: {
  field: FieldSpec
  draft: PlumberConfig
  invalidFields: Partial<Record<keyof PlumberConfig, string>>
  disabled?: boolean
  onChange: <K extends keyof PlumberConfig>(key: K, raw: PlumberConfig[K]) => void
}) {
  const invalidMessage = invalidFields[field.key]

  return (
    <label className={`block space-y-1.5 ${disabled ? 'opacity-55' : ''}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-theme-text">{field.label}</span>
        {field.badge ? (
          <RiskBadge label={field.badge} className={field.badgeClass ?? 'border-theme-border text-theme-muted'} />
        ) : null}
      </div>
      <p className="text-[11px] leading-relaxed text-theme-muted">{field.description}</p>
      {field.type === 'boolean' ? (
        <input
          type="checkbox"
          checked={Boolean(draft[field.key])}
          disabled={disabled}
          onChange={(event) =>
            onChange(field.key, event.target.checked as PlumberConfig[typeof field.key])
          }
          className="mt-1 h-4 w-4 rounded border-theme-border bg-theme-base accent-theme-accent"
        />
      ) : field.type === 'number' ? (
        <>
          <input
            type="number"
            step={field.step}
            value={Number(draft[field.key])}
            onChange={(event) => {
              const parsed = parseNumericField(event.target.value)
              if (parsed === null) {
                onChange(field.key, Number.NaN as PlumberConfig[typeof field.key])
                return
              }
              onChange(field.key, parsed as PlumberConfig[typeof field.key])
            }}
            aria-invalid={invalidMessage ? true : undefined}
            className={`${INPUT_CLASS}${invalidMessage ? ' border-red-500/60 focus:border-red-500/60 focus:ring-red-500/30' : ''}`}
          />
          {invalidMessage ? (
            <p className="text-[10px] text-red-500" role="alert">
              {invalidMessage}
            </p>
          ) : null}
        </>
      ) : (
        <input
          type={field.type === 'password' ? 'password' : 'text'}
          value={String(draft[field.key])}
          onChange={(event) =>
            onChange(field.key, event.target.value as PlumberConfig[typeof field.key])
          }
          autoComplete={field.type === 'password' ? 'off' : undefined}
          className={INPUT_CLASS}
        />
      )}
      {disabled ? (
        <p className="text-[10px] text-emerald-600 dark:text-emerald-400">
          Unavailable while Strict Read Only protects the graph.
        </p>
      ) : null}
    </label>
  )
}

function TrustSectionCard({
  section,
  draft,
  expanded,
  invalidFields,
  onToggle,
  onChange,
}: {
  section: TrustSection
  draft: PlumberConfig
  expanded: boolean
  invalidFields: Partial<Record<keyof PlumberConfig, string>>
  onToggle: () => void
  onChange: <K extends keyof PlumberConfig>(key: K, raw: PlumberConfig[K]) => void
}) {
  const emoji = section.id === 'safe' ? '🟢' : section.id === 'augmented' ? '🟠' : '🔴'

  return (
    <section className={`rounded-xl border ${section.borderClass} bg-theme-base/60`}>
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-start justify-between gap-3 px-4 py-3 text-left transition-all hover:bg-theme-surface/30"
      >
        <div>
          <p className="text-xs font-semibold text-theme-text">
            {emoji} {section.title}
          </p>
          <p className="mt-1 text-[11px] leading-relaxed text-theme-muted">{section.subtitle}</p>
        </div>
        <span className="shrink-0 text-theme-muted">
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            className="h-[30px] w-[30px]"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            {expanded ? <path d="M18 15 12 9 6 15" /> : <path d="M6 9 12 15 18 9" />}
          </svg>
        </span>
      </button>
      {expanded ? (
        <div className="grid grid-cols-2 gap-x-6 gap-y-5 border-t border-theme-border/50 px-4 py-4">
          {section.fields.map((field) => (
            <ConfigField
              key={field.key}
              field={field}
              draft={draft}
              invalidFields={invalidFields}
              disabled={draft.read_only && Boolean(field.writesGraph)}
              onChange={onChange}
            />
          ))}
        </div>
      ) : null}
    </section>
  )
}

export function SettingsDrawer({ open, config, onClose, onSave }: SettingsDrawerProps) {
  const [draft, setDraft] = useState<PlumberConfig>(emptyPlumberConfig())
  const [isDirty, setIsDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [invalidFields, setInvalidFields] = useState<Partial<Record<keyof PlumberConfig, string>>>({})
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    safe: true,
    augmented: true,
    surgeon: true,
  })

  const effectiveDraft = isDirty ? draft : (config ?? emptyPlumberConfig())

  const configLoaded = config !== null

  const requestClose = () => {
    if (isDirty && !window.confirm('Discard unsaved settings changes?')) {
      return
    }
    setSaved(false)
    setIsDirty(false)
    setSaveError(null)
    setInvalidFields({})
    onClose()
  }

  const updateField = <K extends keyof PlumberConfig>(key: K, raw: PlumberConfig[K]) => {
    setDraft((prev) => {
      const base = isDirty ? prev : (config ?? emptyPlumberConfig())
      return { ...base, [key]: raw }
    })
    setIsDirty(true)
    setSaved(false)
    setSaveError(null)
    if (NUMERIC_FIELDS.has(key)) {
      setInvalidFields((prev) => {
        const next = { ...prev }
        if (typeof raw === 'number' && !Number.isNaN(raw)) {
          delete next[key]
        } else {
          next[key] = 'Enter a valid number'
        }
        return next
      })
    }
  }

  const validateDraft = (): boolean => {
    const nextInvalid: Partial<Record<keyof PlumberConfig, string>> = {}
    for (const key of NUMERIC_FIELDS) {
      const value = effectiveDraft[key]
      if (typeof value !== 'number' || Number.isNaN(value) || !Number.isFinite(value)) {
        nextInvalid[key] = 'Enter a valid number'
      }
    }
    setInvalidFields(nextInvalid)
    return Object.keys(nextInvalid).length === 0
  }

  const handleSave = async () => {
    if (!configLoaded) {
      setSaveError('Configuration is still loading. Wait a moment and try again.')
      return
    }
    if (!validateDraft()) {
      setSaveError('Fix invalid numeric fields before saving.')
      return
    }
    setSaving(true)
    setSaveError(null)
    try {
      const result = await onSave(effectiveDraft)
      setSaving(false)
      if (result) {
        setSaved(true)
        setIsDirty(false)
        setSaveError(null)
        return
      }
      setSaveError('Could not save settings. Check the API connection and try again.')
    } catch (error) {
      setSaving(false)
      const message =
        error instanceof Error && error.message.trim()
          ? error.message
          : 'Could not save settings. Check the API connection and try again.'
      setSaveError(message)
    }
  }

  const toggleSection = (id: string) => {
    setExpandedSections((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  return (
    <>
      <div
        className={`fixed inset-0 z-40 bg-theme-base/60 backdrop-blur-sm transition-opacity duration-300 ${
          open ? 'pointer-events-auto opacity-100' : 'pointer-events-none opacity-0'
        }`}
        onClick={requestClose}
        aria-hidden={!open}
      />
      <aside
        className={`fixed inset-y-0 left-0 z-50 h-full w-full overflow-hidden rounded-r-3xl border-r border-theme-border/60 bg-theme-surface/95 shadow-2xl backdrop-blur-md transition-transform duration-300 ease-out ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
        inert={!open}
        aria-hidden={!open}
        aria-label="Environment settings"
      >
        <div className="flex h-full flex-col">
          <header className="flex items-start justify-between gap-4 border-b border-theme-border/50 px-5 py-4">
            <div className="min-w-0">
              <p className="text-[10px] font-medium uppercase tracking-[0.35em] text-theme-muted">
                Configuration
              </p>
              <h2 className="mt-1 text-sm font-semibold text-theme-text">Trust &amp; Safety</h2>
              <p className="mt-1 text-xs text-theme-muted">
                Changes persist to <code className="text-theme-accent">.env</code>. Restart a running daemon to apply runtime-policy changes.
              </p>
            </div>
            <button
              type="button"
              onClick={requestClose}
              aria-label="Close settings"
              className="inline-flex h-9 shrink-0 items-center gap-2 rounded-full bg-theme-text px-4 text-white shadow-sm transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-theme-accent/50 dark:text-theme-accent-foreground"
            >
              <svg
                aria-hidden="true"
                viewBox="0 0 24 24"
                className="h-4 w-4"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              >
                <path d="M18 6 6 18" />
                <path d="m6 6 12 12" />
              </svg>
              <span className="text-[10px] font-semibold uppercase tracking-[0.2em]">CLOSE</span>
            </button>
          </header>

          <form
            className="markdown-theme terminal-scroll flex-1 overflow-y-auto px-5 py-4 text-sm"
            onSubmit={(event) => {
              event.preventDefault()
              void handleSave()
            }}
          >
            <div className="space-y-6">
              <div>
                <p className="mb-3 text-[10px] font-medium uppercase tracking-[0.3em] text-theme-muted">
                  Runtime Policy
                </p>
                <div className="grid grid-cols-2 gap-x-6 gap-y-5 rounded-xl border border-theme-border/50 bg-theme-base/60 p-4">
                  {RUNTIME_POLICY_FIELDS.map((field) => (
                    <ConfigField
                      key={field.key}
                      field={field}
                      draft={effectiveDraft}
                      invalidFields={invalidFields}
                      onChange={updateField}
                    />
                  ))}
                </div>
                <p className="mt-2 text-[11px] leading-relaxed text-theme-muted">
                  These controls are independent: Read Only governs vault writes; Shadow governs only the external derived cache.
                </p>
              </div>

              <div>
                <p className="mb-3 text-[10px] font-medium uppercase tracking-[0.3em] text-theme-muted">
                  Infrastructure
                </p>
                <div className="grid grid-cols-2 gap-x-6 gap-y-5">
                  {INFRA_FIELDS.map((field) =>
                    field.type === 'lm-model' ? (
                      <LmModelField
                        key={field.key}
                        open={open}
                        field={field}
                        lmStudioUrl={effectiveDraft.lm_studio_url}
                        value={effectiveDraft.lm_model}
                        onChange={(model) => updateField('lm_model', model)}
                      />
                    ) : (
                      <ConfigField
                        key={field.key}
                        field={field}
                        draft={effectiveDraft}
                        invalidFields={invalidFields}
                        onChange={updateField}
                      />
                    ),
                  )}
                </div>
              </div>

              <div>
                <p className="mb-3 text-[10px] font-medium uppercase tracking-[0.3em] text-theme-muted">
                  Invasiveness Matrix
                </p>
                <div className="space-y-3">
                  {TRUST_SECTIONS.map((section) => (
                    <TrustSectionCard
                      key={section.id}
                      section={section}
                      draft={effectiveDraft}
                      expanded={expandedSections[section.id] ?? true}
                      invalidFields={invalidFields}
                      onToggle={() => toggleSection(section.id)}
                      onChange={updateField}
                    />
                  ))}
                </div>
              </div>
            </div>
          </form>

          <footer className="space-y-2 border-t border-theme-border/50 px-5 py-4">
            {!configLoaded ? (
              <p className="text-[11px] text-theme-muted">Loading configuration from the API…</p>
            ) : null}
            {saveError ? (
              <p className="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-[11px] text-red-500" role="alert">
                {saveError}
              </p>
            ) : null}
            <button
              type="button"
              disabled={saving || !configLoaded}
              onClick={() => void handleSave()}
              className="w-full rounded-xl border border-theme-accent/80 bg-theme-accent px-4 py-2.5 text-sm font-medium text-theme-accent-foreground transition hover:bg-theme-accent/90 disabled:opacity-50"
            >
              {saving ? 'Saving…' : saved ? 'Saved & Applied ✓' : 'Save & Apply Changes'}
            </button>
          </footer>
        </div>
      </aside>
    </>
  )
}
