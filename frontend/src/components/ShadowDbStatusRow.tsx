import type { ShadowDbState } from '../types/daemon'
import { DEFAULT_SHADOW_DB_STATE } from '../types/daemon'

const STATE_LABELS: Record<ShadowDbState['state'], string> = {
  disabled: 'Disabled',
  bootstrapping: 'Bootstrapping',
  ready: 'Ready',
  stale: 'Stale',
  error: 'Error',
}

const STATE_CLASSES: Record<ShadowDbState['state'], string> = {
  disabled: 'border-theme-border/50 bg-theme-base/40 text-theme-muted',
  bootstrapping: 'border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300',
  ready: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
  stale: 'border-orange-500/40 bg-orange-500/10 text-orange-700 dark:text-orange-300',
  error: 'border-rose-500/40 bg-rose-500/10 text-rose-700 dark:text-rose-300',
}

interface ShadowDbStatusRowProps {
  shadowDb: ShadowDbState | undefined
}

export function ShadowDbStatusRow({ shadowDb }: ShadowDbStatusRowProps) {
  const snapshot = shadowDb ?? DEFAULT_SHADOW_DB_STATE

  const detailParts: string[] = []
  if (snapshot.last_full_sync_at) {
    detailParts.push(`Last full sync ${snapshot.last_full_sync_at}`)
  }
  if (snapshot.source_page_count != null && snapshot.indexed_page_count != null) {
    detailParts.push(
      `Indexed ${snapshot.indexed_page_count} / ${snapshot.source_page_count} pages`,
    )
  }
  if (snapshot.lag_pages != null && snapshot.lag_pages > 0) {
    detailParts.push(`Lag ${snapshot.lag_pages} pages`)
  }
  if (snapshot.last_sync_error) {
    detailParts.push(snapshot.last_sync_error)
  }

  return (
    <section
      className="shrink-0 rounded-2xl bg-theme-surface/45 px-4 py-3 shadow-sm ring-1 ring-theme-border/25 dark:bg-theme-surface/20"
      aria-label="Shadow DB health"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium uppercase tracking-[0.25em] text-theme-muted">
          Shadow DB
        </span>
        <span
          className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider ${STATE_CLASSES[snapshot.state]}`}
        >
          {STATE_LABELS[snapshot.state]}
        </span>
        {!snapshot.enabled && (
          <span className="text-[10px] font-medium uppercase tracking-wider text-theme-muted">
            Flag off
          </span>
        )}
      </div>
      {detailParts.length > 0 && (
        <p className="mt-2 text-xs text-theme-muted">{detailParts.join(' · ')}</p>
      )}
    </section>
  )
}
