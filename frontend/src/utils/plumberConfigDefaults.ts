import type { PlumberConfig } from '../types/daemon'

/** Safe defaults when ``GET /api/config`` has not loaded yet (pre-flight graph save). */
export function emptyPlumberConfig(): PlumberConfig {
  return {
    logseq_graph_path: '',
    read_only: false,
    shadow_db_enabled: true,
    lm_studio_url: 'http://localhost:1234/v1',
    lm_model: 'local-model',
    llm_api_key_configured: false,
    low_priority_mode: true,
    thermal_delay_bootstrap: 2,
    thermal_delay_cognitive: 2,
    mapreduce_trigger_chars: 25000,
    mapreduce_chunk_chars: 15000,
    context_compression: false,
    compression_trigger: 100_000,
    compression_target: 30_000,
    semantic_routing: false,
    entity_consolidation: false,
    property_hygiene: false,
    marpa_framework: false,
    heal_dangling: false,
    backpropagate_links: false,
    enable_inline_semantic_corrections: false,
    auto_split: false,
  }
}
