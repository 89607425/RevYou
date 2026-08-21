import { Tag, Typography, Row, Col, Statistic, Progress, List, Card } from 'antd'
import { SEVERITY_META } from '../api/client'
import type { ReviewReport } from '../api/client'

const { Title, Text, Paragraph } = Typography

export default function SummaryCard({ report }: { report: ReviewReport }) {
  const { summary, cross_summary } = report
  const severityOrder = ['critical', 'major', 'minor', 'suggestion']

  return (
    <Card style={{ marginBottom: 16 }}>
      <Row gutter={24}>
        <Col span={6}>
          <Statistic
            title="综合评分"
            value={summary.overall_score}
            suffix="/ 100"
            valueStyle={{
              color: summary.overall_score >= 70 ? '#3f8600' :
                     summary.overall_score >= 50 ? '#faad14' : '#cf1322',
            }}
          />
        </Col>
        <Col span={18}>
          <Paragraph strong style={{ marginBottom: 8 }}>
            {summary.readiness_verdict}
          </Paragraph>
          <Row gutter={12}>
            {severityOrder.map((sev) => (
              <Col key={sev}>
                <Tag color={SEVERITY_META[sev].color}>
                  {SEVERITY_META[sev].label}: {summary.severity_counts[sev] || 0}
                </Tag>
              </Col>
            ))}
            <Col>
              <Tag>交叉认同: {cross_summary.agreements}</Tag>
            </Col>
            <Col>
              <Tag>交叉异议: {cross_summary.disagreements}</Tag>
            </Col>
          </Row>
        </Col>
      </Row>

      {summary.top_risks.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <Title level={5}>Top 风险</Title>
          <List
            size="small"
            dataSource={summary.top_risks.slice(0, 5)}
            renderItem={(issue) => (
              <List.Item>
                <Text>
                  <Tag color={SEVERITY_META[issue.severity]?.color}>
                    {SEVERITY_META[issue.severity]?.label}
                  </Tag>
                  <Text strong>[{issue.id}]</Text> {issue.title}
                  <Text type="secondary"> @ {issue.location}</Text>
                </Text>
              </List.Item>
            )}
          />
        </div>
      )}
    </Card>
  )
}
