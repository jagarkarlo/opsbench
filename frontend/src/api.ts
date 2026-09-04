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
  run: { run_id: string; runner_kind: string; model_name?: string; started_at: string }
  report: { scenario_id: string; total: number; maximum: number; explanation: string }
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
