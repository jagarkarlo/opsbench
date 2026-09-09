export type Scenario = {
  scenario_id: string
  title: string
  category: string
  pack_hash?: string
}

export type Ranking = {
  runner_name: string
  scenario_count: number
  trial_count: number
  average_score: number
  conservative_score: number
  confidence_interval_95?: [number, number]
}

export type Run = {
  run: {
    run_id: string
    runner_kind: string
    model_name?: string
    started_at: string
    run_schema_version?: string
    scenario_pack_hash?: string
    evaluator_profile_hash?: string
    response_hash?: string
    metadata?: Record<string, string>
  }
  report: {
    scenario_id: string
    total: number
    maximum: number
    explanation: string
    diagnosis?: number
    evidence?: number
    actions?: number
    safety?: number
  }
}

export type Capability = { id: string; label: string; mode: 'ui' | 'cli' }

export type Verification = {
  verification_id: string
  scenario_id: string
  outcome: 'passed' | 'failed' | 'unknown'
  coverage: { ratio: number; tested_stage_count: number; total_stage_count: number }
  assertions: { assertion_id: string; stage_id: string; status: 'passed' | 'failed' | 'unknown' | 'not_tested'; description: string }[]
  observations: { stage_id: string; status: 'passed' | 'failed' | 'unknown' | 'not_tested'; observed_at?: string; evidence_refs: string[]; summary: string }[]
  schema_version: string
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path)
  if (!response.ok) throw new Error(`API request failed: ${response.status}`)
  return response.json() as Promise<T>
}

export function loadScenarios(): Promise<{ scenarios: Scenario[] }> {
  return getJson('/api/v1/scenarios')
}

export function loadPortfolio(): Promise<{ leaderboard: Ranking[] }> {
  return getJson('/api/v1/leaderboard/portfolio')
}

export function loadRuns(): Promise<{ runs: Run[]; count: number }> {
  return getJson('/api/v1/runs?limit=100')
}

export function loadRun(runId: string): Promise<Run> {
  return getJson(`/api/v1/runs/${encodeURIComponent(runId)}`)
}

export function loadHealth(): Promise<{ status: string; version: string }> {
  return getJson('/api/v1/health')
}

export function loadCapabilities(): Promise<{ frontend: boolean; operations: Capability[] }> {
  return getJson('/api/v1/capabilities')
}

export function loadVerification(): Promise<{ count: number; verifications: Verification[] }> {
  return fetch('/api/v1/verifications').then(async response => {
    if (response.status === 404) return { count: 0, verifications: [] }
    if (!response.ok) throw new Error(`API request failed: ${response.status}`)
    return response.json() as Promise<{ count: number; verifications: Verification[] }>
  })
}
