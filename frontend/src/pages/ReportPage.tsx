import { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Typography, Spin, Button, Steps, Tag, Space, message, Tabs, Result, Alert,
} from 'antd'
import {
  ArrowLeftOutlined, DownloadOutlined, CheckCircleOutlined,
  CloseCircleOutlined, LoadingOutlined,
} from '@ant-design/icons'
import {
  subscribeEvents, getJob, getTrace,
  ROLE_LABELS, SEVERITY_META,
  type ReviewReport, type ThinkingStep,
} from '../api/client'
import SummaryCard from '../components/SummaryCard'
import AgentSection from '../components/AgentSection'
import CrossReviewPanel, { ThinkingTracePanel } from '../components/CrossReviewPanel'

const { Title, Text } = Typography

const STAGES = [
  { key: 'parsing', title: '文档解析' },
  { key: 'phase1', title: '三视角独立审查' },
  { key: 'phase2', title: '交叉审查' },
  { key: 'aggregating', title: '报告聚合' },
  { key: 'done', title: '完成' },
]

const STEP_LABELS: Record<string, string> = {
  plan: '规划', execute: '执行', reflect: '反思',
  adjust: '补审', consolidate: '汇总',
}

interface AgentProgress {
  phase: string
  step: string
  focus_area: string
  history: { step: string; focus: string }[]
}

export default function ReportPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const [status, setStatus] = useState<string>('loading')
  const [report, setReport] = useState<ReviewReport | null>(null)
  const [error, setError] = useState<string>('')
  const [agentProgress, setAgentProgress] = useState<Record<string, AgentProgress>>({})
  const [traceSteps, setTraceSteps] = useState<ThinkingStep[]>([])
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!jobId) return

    // First check existing state
    getJob(jobId).then((job) => {
      if (job.status === 'done' && job.report) {
        setReport(job.report)
        setStatus('done')
        getTrace(jobId).then((t) => setTraceSteps(t.steps)).catch(() => {})
      } else if (job.status === 'failed') {
        setError(job.error || '审查失败')
        setStatus('failed')
      } else {
        setStatus(job.status)
      }
    }).catch(() => setStatus('error'))

    // Subscribe to SSE
    const es = subscribeEvents(jobId, (event) => {
      if (event.type === 'status') {
        setStatus(event.status)
      } else if (event.type === 'thinking') {
        setAgentProgress((prev) => {
          const cur = prev[event.agent] || { phase: '', step: '', focus_area: '', history: [] }
          return {
            ...prev,
            [event.agent]: {
              phase: event.phase,
              step: event.step,
              focus_area: event.focus_area,
              history: [
                ...cur.history,
                { step: event.step, focus: event.focus_area },
              ].slice(-30),
            },
          }
        })
      } else if (event.type === 'agent_done') {
        const label = ROLE_LABELS[event.agent] || event.agent
        if (event.phase === 'phase1') {
          message.info(`${label} 独立审查完成: ${event.issue_count} 个问题, 评分 ${event.score}`)
        } else {
          message.info(`${label} 交叉审查完成: ${event.new_issues} 个新问题`)
        }
      } else if (event.type === 'done') {
        setReport(event.report)
        setStatus('done')
        getTrace(jobId).then((t) => setTraceSteps(t.steps)).catch(() => {})
      } else if (event.type === 'failed') {
        setError(event.error)
        setStatus('failed')
      }
    })
    esRef.current = es

    return () => {
      es.close()
    }
  }, [jobId])

  const exportReport = (format: 'md' | 'json') => {
    if (!report) return
    let content: string
    let filename: string

    if (format === 'json') {
      content = JSON.stringify(report, null, 2)
      filename = `review-${jobId}.json`
    } else {
      content = buildMarkdownReport(report)
      filename = `review-${jobId}.md`
    }

    const blob = new Blob([content], {
      type: format === 'json' ? 'application/json' : 'text/markdown',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  const currentStageIdx = STAGES.findIndex(
    (s) => s.key === (status === 'loading' ? 'parsing' : status)
  )

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '24px' }}>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/')}>
          返回
        </Button>
        <Title level={4} style={{ margin: 0 }}>
          {report?.document_title || `审查任务 ${jobId}`}
        </Title>
      </Space>

      {/* Progress panel */}
      {(status !== 'done' && status !== 'failed') && (
        <Card style={{ marginBottom: 16 }}>
          <Steps
            size="small"
            current={Math.max(0, currentStageIdx)}
            items={STAGES.map((s) => ({ title: s.title }))}
          />
          <div style={{ marginTop: 24 }}>
            {Object.entries(AGENT_DISPLAY).map(([role, label]) => {
              const p = agentProgress[role]
              return (
                <div key={role} style={{ marginBottom: 12 }}>
                  <Space>
                    <Tag color="blue">{label}</Tag>
                    {p ? (
                      <>
                        <Tag color={p.phase === 'phase1' ? 'geekblue' : 'purple'}>
                          {p.phase === 'phase1' ? '独立审查' : '交叉审查'}
                        </Tag>
                        <Text>
                          <LoadingOutlined /> {STEP_LABELS[p.step] || p.step}
                          {p.focus_area && <Text type="secondary"> · {p.focus_area}</Text>}
                        </Text>
                        <Text type="secondary">
                          (已执行 {p.history.length} 步)
                        </Text>
                      </>
                    ) : (
                      <Text type="secondary">等待中…</Text>
                    )}
                  </Space>
                </div>
              )
            })}
          </div>
        </Card>
      )}

      {status === 'failed' && (
        <Result
          status="error"
          title="审查失败"
          subTitle={error}
          extra={<Button type="primary" onClick={() => navigate('/')}>重新提交</Button>}
        />
      )}

      {/* Final report */}
      {status === 'done' && report && (
        <>
          <Space style={{ marginBottom: 16 }}>
            <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 20 }} />
            <Title level={4} style={{ margin: 0 }}>审查完成</Title>
            <Button icon={<DownloadOutlined />} onClick={() => exportReport('md')}>
              导出 Markdown
            </Button>
            <Button icon={<DownloadOutlined />} onClick={() => exportReport('json')}>
              导出 JSON
            </Button>
          </Space>

          <SummaryCard report={report} />

          <Tabs
            items={[
              {
                key: 'agents',
                label: '三视角报告',
                children: (
                  <Card>
                    {Object.entries(report.agents).map(([role, r]) => (
                      <div key={role} style={{ marginBottom: 32 }}>
                        <AgentSection
                          role={role}
                          verdict={r.verdict}
                          score={r.overall_score}
                          highlights={r.highlights}
                          issues={r.issues}
                          plan={r.review_plan}
                          callCount={r.call_count}
                        />
                      </div>
                    ))}
                  </Card>
                ),
              },
              {
                key: 'cross',
                label: '交叉审查',
                children: (
                  <Card>
                    <CrossReviewPanel crossReview={report.cross_review} />
                  </Card>
                ),
              },
              {
                key: 'trace',
                label: `思考轨迹 (${traceSteps.length})`,
                children: (
                  <Card>
                    <ThinkingTracePanel steps={traceSteps} />
                  </Card>
                ),
              },
            ]}
          />
        </>
      )}

      {status === 'loading' && (
        <div style={{ textAlign: 'center', padding: 60 }}>
          <Spin size="large" />
          <div style={{ marginTop: 16 }}>
            <Text type="secondary">正在连接任务…</Text>
          </div>
        </div>
      )}
    </div>
  )
}

const AGENT_DISPLAY: Record<string, string> = {
  product_manager: '产品 Agent',
  developer: '开发 Agent',
  tester: '测试 Agent',
}

function buildMarkdownReport(report: ReviewReport): string {
  const lines: string[] = []
  lines.push(`# 需求审查报告: ${report.document_title}`)
  lines.push('')
  lines.push(`- 综合评分: ${report.summary.overall_score}/100`)
  lines.push(`- 结论: ${report.summary.readiness_verdict}`)
  lines.push(`- 严重度分布: ${JSON.stringify(report.summary.severity_counts)}`)
  lines.push('')

  for (const [role, r] of Object.entries(report.agents)) {
    lines.push(`## ${ROLE_LABELS[role] || role} (评分: ${r.overall_score})`)
    lines.push('')
    lines.push(r.verdict)
    lines.push('')
    if (r.issues.length) {
      lines.push('| 严重度 | ID | 位置 | 问题 | 建议 |')
      lines.push('|---|---|---|---|---|')
      for (const i of r.issues) {
        lines.push(
          `| ${SEVERITY_META[i.severity]?.label || i.severity} | ${i.id} | ` +
          `${i.location} | ${i.title} | ${i.suggestion} |`
        )
      }
      lines.push('')
    }
  }

  lines.push('## 交叉审查')
  for (const [role, r] of Object.entries(report.cross_review)) {
    lines.push(`### ${ROLE_LABELS[role] || role}`)
    for (const a of r.peer_agreements || []) {
      lines.push(`- 认同 [${a.peer_issue_id}]: ${a.comment}`)
    }
    for (const d of r.peer_disagreements || []) {
      lines.push(`- 异议 [${d.peer_issue_id}]: ${d.reason || d.comment}`)
    }
  }

  return lines.join('\n')
}
