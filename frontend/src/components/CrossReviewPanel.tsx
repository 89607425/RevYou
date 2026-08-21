import { Card, Tag, List, Typography, Collapse, Badge } from 'antd'
import { ROLE_LABELS, SEVERITY_META } from '../api/client'
import type { AgentPhase2Report } from '../api/client'

const { Text, Paragraph } = Typography

const STEP_LABELS: Record<string, string> = {
  plan: '规划',
  execute: '执行',
  reflect: '反思',
  adjust: '补审',
  consolidate: '汇总',
}

export function ThinkingTracePanel({ steps }: { steps: any[] }) {
  if (!steps.length) return <Text type="secondary">暂无思考轨迹</Text>
  return (
    <Collapse
      size="small"
      items={steps.map((s, i) => ({
        key: i,
        label: (
          <span>
            <Tag color={s.phase === 'phase1' ? 'blue' : 'purple'}>
              {s.phase === 'phase1' ? '独立审查' : '交叉审查'}
            </Tag>
            <Tag>{ROLE_LABELS[s.agent_role] || s.agent_role}</Tag>
            <Tag color="geekblue">{STEP_LABELS[s.step] || s.step}</Tag>
            {s.focus_area && <Text type="secondary">{s.focus_area}</Text>}
          </span>
        ),
        children: (
          <pre style={{
            maxHeight: 300, overflow: 'auto', fontSize: 12,
            background: '#f5f5f5', padding: 12, borderRadius: 6,
          }}>
            {(() => {
              try { return JSON.stringify(JSON.parse(s.raw_output), null, 2) }
              catch { return s.raw_output }
            })()}
          </pre>
        ),
      }))}
    />
  )
}

export default function CrossReviewPanel({
  crossReview,
}: {
  crossReview: Record<string, AgentPhase2Report>
}) {
  const entries = Object.entries(crossReview).filter(
    ([, r]) => r.peer_agreements?.length || r.peer_disagreements?.length || r.new_issues?.length
  )
  if (!entries.length) {
    return <Text type="secondary">暂无交叉审查数据</Text>
  }

  return (
    <div>
      {entries.map(([role, r]) => (
        <Card key={role} size="small" style={{ marginBottom: 12 }}
              title={ROLE_LABELS[role] || role}>
          {r.peer_agreements?.length > 0 && (
            <div style={{ marginBottom: 8 }}>
              <Badge status="success" text={`认同同行 (${r.peer_agreements.length})`} />
              <List
                size="small"
                dataSource={r.peer_agreements}
                renderItem={(a: any) => (
                  <List.Item style={{ padding: '4px 0' }}>
                    <Text>
                      <Tag color="green">{a.peer_issue_id}</Tag>
                      {a.comment}
                    </Text>
                  </List.Item>
                )}
              />
            </div>
          )}
          {r.peer_disagreements?.length > 0 && (
            <div style={{ marginBottom: 8 }}>
              <Badge status="error" text={`异议 (${r.peer_disagreements.length})`} />
              <List
                size="small"
                dataSource={r.peer_disagreements}
                renderItem={(d: any) => (
                  <List.Item style={{ padding: '4px 0' }}>
                    <Text>
                      <Tag color="red">{d.peer_issue_id}</Tag>
                      {d.reason || d.comment}
                    </Text>
                  </List.Item>
                )}
              />
            </div>
          )}
          {r.new_issues?.length > 0 && (
            <div>
              <Badge status="warning" text={`交叉审查新发现 (${r.new_issues.length})`} />
              <List
                size="small"
                dataSource={r.new_issues}
                renderItem={(issue) => (
                  <List.Item style={{ padding: '4px 0' }}>
                    <Text>
                      <Tag color={SEVERITY_META[issue.severity]?.color}>
                        {SEVERITY_META[issue.severity]?.label}
                      </Tag>
                      <Text strong>[{issue.id}]</Text> {issue.title}
                    </Text>
                  </List.Item>
                )}
              />
            </div>
          )}
          {r.severity_adjustments?.length > 0 && (
            <Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0 }}>
              严重度调整: {r.severity_adjustments.map((a) =>
                `${a.issue_id} ${a.from}→${a.to}`).join('; ')}
            </Paragraph>
          )}
        </Card>
      ))}
    </div>
  )
}
