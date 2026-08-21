import { Table, Tag, Typography, Collapse, Timeline } from 'antd'
import { ROLE_LABELS, SEVERITY_META } from '../api/client'
import type { Issue, ReviewPlan } from '../api/client'

const { Paragraph, Text } = Typography

export function IssueList({ issues }: { issues: Issue[] }) {
  const sorted = [...issues].sort((a, b) => {
    const order = { critical: 0, major: 1, minor: 2, suggestion: 3 }
    return (order[a.severity] ?? 9) - (order[b.severity] ?? 9)
  })

  return (
    <Table
      dataSource={sorted}
      rowKey="id"
      size="small"
      pagination={{ pageSize: 10, hideOnSinglePage: true }}
      columns={[
        {
          title: '严重度',
          dataIndex: 'severity',
          width: 80,
          render: (s: string) => (
            <Tag color={SEVERITY_META[s]?.color}>{SEVERITY_META[s]?.label || s}</Tag>
          ),
        },
        { title: 'ID', dataIndex: 'id', width: 90 },
        { title: '位置', dataIndex: 'location', width: 160, ellipsis: true },
        { title: '问题', dataIndex: 'title' },
      ]}
      expandable={{
        expandedRowRender: (record) => (
          <div style={{ padding: '8px 0' }}>
            <Paragraph><Text strong>描述: </Text>{record.description}</Paragraph>
            {record.suggestion && (
              <Paragraph><Text strong>建议: </Text>{record.suggestion}</Paragraph>
            )}
          </div>
        ),
      }}
    />
  )
}

export function PlanTrace({ plan }: { plan?: ReviewPlan }) {
  if (!plan) return null
  return (
    <div style={{ padding: '8px 0' }}>
      <Paragraph>
        <Text strong>文档分析: </Text>
        {plan.document_analysis.doc_type} · 复杂度 {plan.document_analysis.complexity_score}/5
        <br />
        <Text type="secondary">{plan.document_analysis.key_observation}</Text>
      </Paragraph>
      <Paragraph>
        <Text strong>Agent 自主规划的审查焦点 ({plan.focus_areas.length} 项):</Text>
      </Paragraph>
      <Timeline
        items={plan.focus_areas.map((fa) => ({
          children: (
            <div>
              <Text strong>{fa.area}</Text>
              {fa.questions.map((q, i) => (
                <div key={i}><Text type="secondary">· {q}</Text></div>
              ))}
            </div>
          ),
        }))}
      />
    </div>
  )
}

export default function AgentSection({
  role, verdict, score, highlights, issues, plan, callCount,
}: {
  role: string
  verdict: string
  score: number
  highlights: string[]
  issues: Issue[]
  plan?: ReviewPlan
  callCount?: number
}) {
  return (
    <div>
      <div style={{ marginBottom: 8, display: 'flex', gap: 8, alignItems: 'center' }}>
        <Typography.Title level={5} style={{ margin: 0 }}>
          {ROLE_LABELS[role] || role}
        </Typography.Title>
        <Tag color={score >= 70 ? 'green' : score >= 50 ? 'orange' : 'red'}>
          评分 {score}
        </Tag>
        {callCount !== undefined && <Tag>LLM 调用 {callCount} 次</Tag>}
      </div>
      <Paragraph type="secondary">{verdict}</Paragraph>

      <Collapse
        size="small"
        style={{ marginBottom: 12 }}
        items={[
          ...(plan ? [{
            key: 'plan',
            label: `审查策略（Agent 自主规划 · ${plan.focus_areas.length} 个焦点）`,
            children: <PlanTrace plan={plan} />,
          }] : []),
          ...(highlights.length ? [{
            key: 'highlights',
            label: `亮点 (${highlights.length})`,
            children: (
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                {highlights.map((h, i) => <li key={i}>{h}</li>)}
              </ul>
            ),
          }] : []),
        ]}
      />

      <IssueList issues={issues} />
    </div>
  )
}
