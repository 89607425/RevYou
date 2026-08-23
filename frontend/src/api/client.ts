export interface Issue {
  id: string
  severity: 'critical' | 'major' | 'minor' | 'suggestion'
  location: string
  title: string
  description: string
  suggestion: string
}

export interface ReviewPlan {
  document_analysis: {
    doc_type: string
    complexity_score: number
    key_observation: string
  }
  risk_areas: { area: string; reason: string; evidence_location: string }[]
  focus_areas: { area: string; questions: string[]; related_sections: string[] }[]
  depth_assessment: number
}

export interface ReflectResult {
  coverage_gaps: string[]
  quality_issues: string[]
  false_positives: string[]
  needs_another_pass: boolean
  gap_areas: string[]
}

export interface AgentPhase1Report {
  role: string
  overall_score: number
  verdict: string
  highlights: string[]
  issues: Issue[]
  review_plan?: ReviewPlan
  reflect_result?: ReflectResult
  call_count: number
}

export interface PeerOpinion {
  peer_issue_id: string
  comment: string
  reason?: string
}

export interface AgentPhase2Report {
  role: string
  peer_agreements: PeerOpinion[]
  peer_disagreements: PeerOpinion[]
  new_issues: Issue[]
  severity_adjustments: {
    issue_id: string
    from: string
    to: string
    reason: string
  }[]
  call_count: number
}

export interface ReviewReport {
  job_id: string
  document_title: string
  source_type: string
  summary: {
    overall_score: number
    severity_counts: Record<string, number>
    role_counts: Record<string, number>
    top_risks: Issue[]
    improvement_suggestions: string[]
    readiness_verdict: string
  }
  agents: Record<string, AgentPhase1Report>
  cross_review: Record<string, AgentPhase2Report>
  cross_summary: {
    agreements: number
    disagreements: number
    typical_disagreements: string[]
  }
}

export interface ThinkingStep {
  agent_role: string
  phase: string
  step: string
  focus_area: string
  raw_output: string
  timestamp: string
}

const API_BASE = ''

export async function startMarkdownReview(content: string): Promise<string> {
  const resp = await fetch(`${API_BASE}/api/review/markdown`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source_type: 'markdown', markdown_content: content }),
  })
  if (!resp.ok) throw new Error(await resp.text())
  const data = await resp.json()
  return data.job_id
}

export async function startFileReview(file: File): Promise<string> {
  const form = new FormData()
  form.append('file', file)
  const resp = await fetch(`${API_BASE}/api/review/file`, {
    method: 'POST',
    body: form,
  })
  if (!resp.ok) throw new Error(await resp.text())
  const data = await resp.json()
  return data.job_id
}

export async function startTapdReview(
  workspace: string,
  storyId: string,
): Promise<string> {
  const resp = await fetch(`${API_BASE}/api/review/tapd`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      source_type: 'tapd',
      tapd_workspace: workspace,
      tapd_story_id: storyId,
    }),
  })
  if (!resp.ok) throw new Error(await resp.text())
  const data = await resp.json()
  return data.job_id
}

export async function getJob(jobId: string): Promise<any> {
  const resp = await fetch(`${API_BASE}/api/jobs/${jobId}`)
  if (!resp.ok) throw new Error(await resp.text())
  return resp.json()
}

export async function getTrace(jobId: string): Promise<{ steps: ThinkingStep[] }> {
  const resp = await fetch(`${API_BASE}/api/jobs/${jobId}/trace`)
  if (!resp.ok) throw new Error(await resp.text())
  return resp.json()
}

export function subscribeEvents(
  jobId: string,
  onEvent: (event: any) => void,
  onError?: (err: any) => void,
): EventSource {
  const es = new EventSource(`${API_BASE}/api/jobs/${jobId}/events`)
  es.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data)
      if (data.type === 'close') {
        es.close()
        return
      }
      if (data.type !== 'heartbeat') {
        onEvent(data)
      }
    } catch {
      // ignore parse errors
    }
  }
  es.onerror = (err) => {
    es.close()
    onError?.(err)
  }
  return es
}

export const ROLE_LABELS: Record<string, string> = {
  product_manager: '产品视角',
  developer: '开发视角',
  tester: '测试视角',
}

export const SEVERITY_META: Record<string, { label: string; color: string }> = {
  critical: { label: '阻断', color: 'red' },
  major: { label: '高', color: 'orange' },
  minor: { label: '中', color: 'gold' },
  suggestion: { label: '建议', color: 'blue' },
}

// ── History API ──────────────────────────────────────────────────────

export interface JobListItem {
  id: string
  status: string
  source_type: string
  document_title: string | null
  source_ref: string | null
  created_at: string
  updated_at: string
  has_report: number
}

export interface JobListResponse {
  items: JobListItem[]
  total: number
  limit: number
  offset: number
}

export async function listJobs(params?: {
  limit?: number
  offset?: number
  status?: string
  source_type?: string
  keyword?: string
}): Promise<JobListResponse> {
  const sp = new URLSearchParams()
  if (params?.limit) sp.set('limit', String(params.limit))
  if (params?.offset) sp.set('offset', String(params.offset))
  if (params?.status) sp.set('status', params.status)
  if (params?.source_type) sp.set('source_type', params.source_type)
  if (params?.keyword) sp.set('keyword', params.keyword)
  const resp = await fetch(`${API_BASE}/api/jobs?${sp.toString()}`)
  if (!resp.ok) throw new Error(await resp.text())
  return resp.json()
}

export async function deleteJob(jobId: string): Promise<void> {
  const resp = await fetch(`${API_BASE}/api/jobs/${jobId}`, { method: 'DELETE' })
  if (!resp.ok) throw new Error(await resp.text())
}

export const SOURCE_TYPE_LABELS: Record<string, string> = {
  markdown: 'Markdown',
  pdf: 'PDF',
  tapd: 'TAPD',
}

export const STATUS_META: Record<string, { label: string; color: string }> = {
  queued: { label: '排队中', color: 'default' },
  parsing: { label: '解析中', color: 'processing' },
  phase1: { label: '独立审查', color: 'processing' },
  phase2: { label: '交叉审查', color: 'processing' },
  aggregating: { label: '聚合中', color: 'processing' },
  done: { label: '已完成', color: 'success' },
  failed: { label: '失败', color: 'error' },
}
