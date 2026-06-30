"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter, useParams } from "next/navigation";
import { Layout, Button, Typography, Space, Tag, Spin, Tabs, Card, Empty, Modal, App, Timeline, Collapse, Progress, Statistic, Row, Col, Drawer } from "antd";
import { ArrowLeftOutlined, StopOutlined, ReloadOutlined, CopyOutlined, LoadingOutlined, CheckCircleOutlined, ExclamationCircleOutlined, ClockCircleOutlined, EyeOutlined, ExpandOutlined, CompressOutlined, DownOutlined, UpOutlined } from "@ant-design/icons";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const { Content } = Layout;
const { Title, Text } = Typography;

interface CrossReviewTag {
  source_agent: string;
  reviewer_agent: string;
  issue_index: number;
  tag: string;
  comment: string;
}

interface ReviewIssue {
  issue_id: string;
  source_agent: string;
  issue_type: string;
  severity: string;
  title: string;
  description: string;
  suggestion?: string;
  prd_section?: string;
  prd_quote?: string;
  confidence: number;
  confidence_label: string;
  cross_review_tags?: CrossReviewTag[];
  status: string;
  review_round: number;
}

interface ThinkingLog {
  id: string;
  agent: string;
  message: string;
  phase: string;
  timestamp: string;
}

const AGENT_LABEL: Record<string, string> = {
  PM_REVIEW: "PM", DEV_REVIEW: "Dev", QA_REVIEW: "QA", SYSTEM: "系统",
};
const AGENT_COLOR: Record<string, string> = {
  PM_REVIEW: "#1677ff", DEV_REVIEW: "#52c41a", QA_REVIEW: "#fa8c16", SYSTEM: "#8c8c8c",
};
const SEVERITY_COLOR: Record<string, string> = { HIGH: "red", MEDIUM: "orange", LOW: "blue" };
const SEVERITY_LABEL: Record<string, string> = { HIGH: "高", MEDIUM: "中", LOW: "低" };

export default function ReviewWorkspacePage() {
  const router = useRouter();
  const params = useParams();
  const sessionId = params.id as string;
  const { message } = App.useApp();
  const wsRef = useRef<WebSocket | null>(null);

  const [session, setSession] = useState<any>(null);
  const [issues, setIssues] = useState<ReviewIssue[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("ALL");
  const [thinkingLogs, setThinkingLogs] = useState<ThinkingLog[]>([]);
  const [agentProgress, setAgentProgress] = useState<Record<string, { status: string; count: number }>>({
    PM_REVIEW: { status: "PENDING", count: 0 },
    DEV_REVIEW: { status: "PENDING", count: 0 },
    QA_REVIEW: { status: "PENDING", count: 0 },
  });
  const [prdVisible, setPrdVisible] = useState(false);
  const [detailIssue, setDetailIssue] = useState<ReviewIssue | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/login"); return; }
    fetchSession();
    connectWebSocket();
    return () => { wsRef.current?.close(); };
  }, [sessionId]);

  const connectWebSocket = () => {
    const token = localStorage.getItem("token");
    const ws = new WebSocket(`ws://localhost:8000/ws/sessions/${sessionId}?token=${token}`);
    wsRef.current = ws;
    ws.onmessage = (event) => {
      try { handleWsMessage(JSON.parse(event.data)); } catch {}
    };
  };

  const handleWsMessage = (data: any) => {
    const { type, payload } = data;
    switch (type) {
      case "AGENT_THINKING":
        setThinkingLogs((prev) => [...prev, {
          id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
          agent: payload.agent, message: payload.message,
          phase: payload.phase, timestamp: payload.timestamp,
        }]);
        break;
      case "ISSUE_CREATED":
        setIssues((prev) => prev.find((i) => i.issue_id === payload.issue_id) ? prev : [...prev, payload]);
        break;
      case "AGENT_STATUS_CHANGED":
        setAgentProgress((prev) => ({ ...prev, [payload.agent]: { status: payload.status, count: payload.issue_count } }));
        break;
      case "SESSION_COMPLETED":
        setSession((prev: any) => prev ? { ...prev, status: "COMPLETED" } : null);
        message.success(`审查完成！共发现 ${payload.issue_count.total} 个问题`);
        fetchIssues();
        break;
      case "SESSION_TIMEOUT":
        setSession((prev: any) => prev ? { ...prev, status: "TIMEOUT" } : null);
        message.warning("审查超时");
        fetchIssues();
        break;
    }
  };

  const fetchSession = async () => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`http://localhost:8000/api/v1/sessions/${sessionId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (data.code === 0) {
        setSession(data.data);
        if (data.data.status === "COMPLETED" || data.data.status === "TIMEOUT") {
          fetchIssues();
        }
      }
    } catch { message.error("获取审查会话失败"); }
    finally { setLoading(false); }
  };

  const fetchIssues = async (agent?: string) => {
    try {
      const token = localStorage.getItem("token");
      const agentParam = agent && agent !== "ALL" ? `&source_agent=${agent}` : "";
      const res = await fetch(`http://localhost:8000/api/v1/sessions/${sessionId}/issues?page=1&page_size=200${agentParam}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (data.code === 0) setIssues(data.data?.items || []);
    } catch {}
  };

  const handleCancel = async () => {
    try {
      const token = localStorage.getItem("token");
      await fetch(`http://localhost:8000/api/v1/sessions/${sessionId}/cancel`, {
        method: "POST", headers: { Authorization: `Bearer ${token}` },
      });
      message.success("审查已终止");
      fetchSession();
    } catch { message.error("操作失败"); }
  };

  const handleIssueAction = async (issueId: string, status: string, note?: string) => {
    try {
      const token = localStorage.getItem("token");
      await fetch(`http://localhost:8000/api/v1/sessions/${sessionId}/issues/${issueId}`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ status, resolution_note: note }),
      });
      message.success(status === "CONFIRMED" ? "已确认" : "已标记为误报");
      fetchIssues(activeTab);
    } catch { message.error("操作失败"); }
  };

  const handleCopyIssue = async (issueId: string) => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`http://localhost:8000/api/v1/sessions/${sessionId}/issues/${issueId}/copy`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (data.code === 0) { await navigator.clipboard.writeText(data.data.copy_text); message.success("已复制"); }
    } catch { message.error("复制失败"); }
  };

  const isRunning = session?.status === "RUNNING";
  const isCompleted = session?.status === "COMPLETED";
  const filteredIssues = activeTab === "ALL" ? issues : issues.filter((i) => i.source_agent === activeTab);

  const agentIssueCounts: Record<string, number> = { ALL: issues.length };
  ["PM_REVIEW", "DEV_REVIEW", "QA_REVIEW"].forEach((a) => {
    agentIssueCounts[a] = issues.filter((i) => i.source_agent === a).length;
  });

  const summary: Record<string, number> = {
    total: issues.length,
    HIGH: issues.filter((i) => i.severity === "HIGH").length,
    MEDIUM: issues.filter((i) => i.severity === "MEDIUM").length,
    LOW: issues.filter((i) => i.severity === "LOW").length,
  };
  Object.keys(agentIssueCounts).filter(k => k !== "ALL").forEach((agent) => {
    const agentIssues = issues.filter((i) => i.source_agent === agent);
    summary[`${agent}_total`] = agentIssues.length;
    ["HIGH", "MEDIUM", "LOW"].forEach((sev) => {
      summary[`${agent}_${sev}`] = agentIssues.filter((i) => i.severity === sev).length;
    });
  });

  if (loading) {
    return <div className="flex items-center justify-center min-h-screen"><Spin size="large" /></div>;
  }

  const renderPhaseIcon = (phase: string) => {
    switch (phase) {
      case "COMPLETED": return <CheckCircleOutlined style={{ color: "#52c41a" }} />;
      case "TIMEOUT": return <ExclamationCircleOutlined style={{ color: "#ff4d4f" }} />;
      case "STARTING": case "READING": return <LoadingOutlined />;
      case "THINKING": return <LoadingOutlined spin />;
      default: return <ClockCircleOutlined />;
    }
  };

  // Agent thinking cards grouped by agent, showing most recent first
  const logsByAgent: Record<string, ThinkingLog[]> = {};
  thinkingLogs.forEach((log) => {
    if (!logsByAgent[log.agent]) logsByAgent[log.agent] = [];
    logsByAgent[log.agent].push(log);
  });
  const agentOrder = ["SYSTEM", "PM_REVIEW", "DEV_REVIEW", "QA_REVIEW"].filter((a) => logsByAgent[a]?.length);

  return (
    <App>
      <Layout style={{ minHeight: "100vh", background: "#f5f5f5" }}>
        {/* ── Header ── */}
        <div className="h-14 bg-white border-b flex items-center justify-between px-4 shadow-sm">
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={() => router.back()}>返回</Button>
            <Title level={5} style={{ margin: 0 }}>{sessionId}</Title>
            {session && (
              <Tag color={isCompleted ? "success" : isRunning ? "processing" : "default"}>
                {isRunning ? "审查中" : isCompleted ? "已完成" : session.status}
              </Tag>
            )}
          </Space>
          <Space>
            {isRunning && <Button danger icon={<StopOutlined />} onClick={handleCancel}>终止审查</Button>}
            {isCompleted && <Button icon={<ReloadOutlined />}>重新审查</Button>}
            <Button
              icon={prdVisible ? <CompressOutlined /> : <ExpandOutlined />}
              onClick={() => setPrdVisible(!prdVisible)}
            >
              {prdVisible ? "隐藏PRD" : "查看PRD"}
            </Button>
          </Space>
        </div>

        <Content style={{ padding: 24, maxWidth: 1200, margin: "0 auto", width: "100%" }}>
          {/* ── PRD Content (collapsible) ── */}
          {prdVisible && (
            <Card title="PRD 文档" className="mb-4" extra={<Button size="small" onClick={() => setPrdVisible(false)}>收起</Button>}>
              <div className="prose max-w-none max-h-96 overflow-auto">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {session?.prd_content || "暂无PRD内容"}
                </ReactMarkdown>
              </div>
            </Card>
          )}

          {/* ── RUNNING: Streaming view ── */}
          {isRunning && (
            <>
              {/* Agent progress bar */}
              <Card size="small" className="mb-4" title="Agent 审查进度">
                <Row gutter={16}>
                  {["PM_REVIEW", "DEV_REVIEW", "QA_REVIEW"].map((agent) => {
                    const p = agentProgress[agent];
                    const percent = p.status === "COMPLETED" ? 100 : p.status === "PENDING" ? 0 : 50;
                    return (
                      <Col span={8} key={agent}>
                        <Progress
                          percent={percent}
                          status={p.status === "COMPLETED" ? "success" : p.status === "PENDING" && !isRunning ? "normal" : "active"}
                          format={() => (
                            <Space size={4}>
                              <Tag color={AGENT_COLOR[agent]}>{AGENT_LABEL[agent]}</Tag>
                              <Text className="text-xs">{p.status === "COMPLETED" ? `${p.count}个问题` : p.status === "PENDING" ? "等待" : "审查中"}</Text>
                            </Space>
                          )}
                        />
                      </Col>
                    );
                  })}
                </Row>
              </Card>

              {/* Streaming thinking logs by agent */}
              {agentOrder.length > 0 ? (
                agentOrder.map((agent) => {
                  const logs = logsByAgent[agent] || [];
                  const lastLog = logs[logs.length - 1];
                  const isActive = lastLog?.phase !== "COMPLETED";
                  return (
                    <Card
                      key={agent}
                      size="small"
                      className="mb-3"
                      title={
                        <Space>
                          <Tag color={AGENT_COLOR[agent]}>{AGENT_LABEL[agent]}</Tag>
                          {isActive ? <LoadingOutlined spin /> : <CheckCircleOutlined style={{ color: "#52c41a" }} />}
                          <Text className="text-sm" type={isActive ? undefined : "secondary"}>
                            {isActive ? "审查中..." : "审查完成"}
                          </Text>
                        </Space>
                      }
                    >
                      <Timeline style={{ marginTop: 8 }}
                        items={logs.slice(-8).map((log) => ({
                          color: log.phase === "COMPLETED" ? "green" : log.phase === "TIMEOUT" ? "red" : "blue",
                          dot: renderPhaseIcon(log.phase),
                          children: <Text className="text-xs">{log.message}</Text>,
                        }))}
                      />
                    </Card>
                  );
                })
              ) : (
                <Card>
                  <div className="text-center py-8">
                    <LoadingOutlined style={{ fontSize: 32, color: "#1677ff" }} />
                    <div className="mt-3 text-gray-500">AI Agent 正在启动审查，请稍候...</div>
                  </div>
                </Card>
              )}
            </>
          )}

          {/* ── COMPLETED: Results view ── */}
          {isCompleted && (
            <>
              {/* Summary cards */}
              <Row gutter={16} className="mb-4">
                <Col span={12}>
                  <Card size="small">
                    <Statistic title="问题总数" value={summary.total} />
                    <Space size={8} className="mt-2">
                      <Tag color="red">高 {summary.HIGH}</Tag>
                      <Tag color="orange">中 {summary.MEDIUM}</Tag>
                      <Tag color="blue">低 {summary.LOW}</Tag>
                    </Space>
                  </Card>
                </Col>
                <Col span={12}>
                  <Card size="small" title="总体评价">
                    <div className="text-sm">
                      {summary.HIGH > 0 ? (
                        <div className="mb-1">⚠ 发现 <Text type="danger">{summary.HIGH} 个高风险问题</Text>，建议立即处理</div>
                      ) : (
                        <div className="mb-1">✅ 无高风险问题</div>
                      )}
                      {summary.MEDIUM > 0 ? (
                        <div className="mb-1">📋 <Text type="warning">{summary.MEDIUM} 个中风险问题</Text>，建议开发前修复</div>
                      ) : null}
                      {summary.LOW > 0 ? (
                        <div>💡 <Text type="secondary">{summary.LOW} 个低风险建议</Text></div>
                      ) : null}
                      {summary.total === 0 && <Text type="success">PRD 质量良好，未发现明显问题</Text>}
                    </div>
                  </Card>
                </Col>
              </Row>

              {/* Agent detail cards */}
              <Row gutter={16} className="mb-4">
                {["PM_REVIEW", "DEV_REVIEW", "QA_REVIEW"].map((agent) => (
                  <Col span={8} key={agent}>
                    <Card
                      size="small"
                      hoverable
                      className="cursor-pointer"
                      title={<Tag color={AGENT_COLOR[agent]}>{AGENT_LABEL[agent]} 审查结果</Tag>}
                      onClick={() => { setActiveTab(agent); fetchIssues(agent); }}
                    >
                      <Statistic value={agentIssueCounts[agent] || 0} suffix="个问题" />
                      <Space size={4} className="mt-1">
                        <Tag color="red" className="text-xs">H {summary[`${agent}_HIGH`] || 0}</Tag>
                        <Tag color="orange" className="text-xs">M {summary[`${agent}_MEDIUM`] || 0}</Tag>
                        <Tag color="blue" className="text-xs">L {summary[`${agent}_LOW`] || 0}</Tag>
                      </Space>
                    </Card>
                  </Col>
                ))}
              </Row>

              {/* Issue list with tabs */}
              <Card
                title="问题详情"
                extra={
                  <Tabs
                    activeKey={activeTab}
                    onChange={(key) => { setActiveTab(key); fetchIssues(key); }}
                    size="small"
                    className="mb-0"
                    items={[
                      { key: "ALL", label: `全部 (${summary.total})` },
                      { key: "PM_REVIEW", label: `PM (${agentIssueCounts["PM_REVIEW"]})` },
                      { key: "DEV_REVIEW", label: `Dev (${agentIssueCounts["DEV_REVIEW"]})` },
                      { key: "QA_REVIEW", label: `QA (${agentIssueCounts["QA_REVIEW"]})` },
                    ]}
                  />
                }
              >
                {filteredIssues.length === 0 ? (
                  <Empty description="暂无问题" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                ) : (
                  <div className="space-y-2">
                    {filteredIssues.map((issue) => (
                      <Card
                        key={issue.issue_id}
                        size="small"
                        hoverable
                        className="transition-all hover:shadow-md"
                        onClick={() => { setDetailIssue(issue); setDetailOpen(true); }}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <Space size={4} className="mb-1">
                              <Tag color={SEVERITY_COLOR[issue.severity]}>{SEVERITY_LABEL[issue.severity]}</Tag>
                              <Tag color={AGENT_COLOR[issue.source_agent]}>{AGENT_LABEL[issue.source_agent]}</Tag>
                              <Text strong className="text-sm">{issue.title}</Text>
                            </Space>
                            <div className="text-xs text-gray-500 truncate">
                              {issue.description.substring(0, 120)}...
                            </div>
                          </div>
                          <Space size={4} className="flex-shrink-0">
                            <Button size="small" type="primary" onClick={(e) => { e.stopPropagation(); handleIssueAction(issue.issue_id, "CONFIRMED"); }}>确认</Button>
                            <Button size="small" danger onClick={(e) => {
                              e.stopPropagation();
                              const note = prompt("请输入误报原因:");
                              if (note) handleIssueAction(issue.issue_id, "FALSE_POSITIVE", note);
                            }}>误报</Button>
                            <Button size="small" icon={<CopyOutlined />} onClick={(e) => { e.stopPropagation(); handleCopyIssue(issue.issue_id); }} />
                          </Space>
                        </div>
                      </Card>
                    ))}
                  </div>
                )}
              </Card>
            </>
          )}
        </Content>
      </Layout>

      {/* ── Issue Detail Drawer ── */}
      <Drawer
        title={detailIssue?.title}
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        width={600}
        extra={
          <Space>
            <Button size="small" type="primary" onClick={() => { handleIssueAction(detailIssue!.issue_id, "CONFIRMED"); setDetailOpen(false); }}>确认</Button>
            <Button size="small" danger onClick={() => {
              const note = prompt("请输入误报原因:");
              if (note) { handleIssueAction(detailIssue!.issue_id, "FALSE_POSITIVE", note); setDetailOpen(false); }
            }}>误报</Button>
            <Button size="small" icon={<CopyOutlined />} onClick={() => handleCopyIssue(detailIssue!.issue_id)}>复制</Button>
          </Space>
        }
      >
        {detailIssue && (
          <div>
            <Space size={8} className="mb-4">
              <Tag color={SEVERITY_COLOR[detailIssue.severity]}>严重程度: {SEVERITY_LABEL[detailIssue.severity]}</Tag>
              <Tag color={AGENT_COLOR[detailIssue.source_agent]}>{AGENT_LABEL[detailIssue.source_agent]}</Tag>
              <Tag>类型: {detailIssue.issue_type}</Tag>
              <Tag>置信度: {detailIssue.confidence?.toFixed(2)}</Tag>
            </Space>

            <div className="mb-4">
              <Title level={5}>问题描述</Title>
              <div className="text-sm whitespace-pre-wrap bg-gray-50 p-3 rounded">{detailIssue.description}</div>
            </div>

            {detailIssue.suggestion && (
              <div className="mb-4">
                <Title level={5}>修复建议</Title>
                <div className="text-sm whitespace-pre-wrap bg-blue-50 p-3 rounded">{detailIssue.suggestion}</div>
              </div>
            )}

            {detailIssue.prd_quote && (
              <div className="mb-4">
                <Title level={5}>PRD 原文引用</Title>
                <div className="text-sm whitespace-pre-wrap bg-yellow-50 p-3 rounded italic">{detailIssue.prd_quote}</div>
              </div>
            )}

            {detailIssue.prd_section && (
              <div className="mb-4">
                <Title level={5}>关联章节</Title>
                <Text className="text-sm">{detailIssue.prd_section}</Text>
              </div>
            )}

            {detailIssue.cross_review_tags && detailIssue.cross_review_tags.length > 0 && (
              <div className="mb-4">
                <Title level={5}>交叉审查</Title>
                <Timeline
                  items={detailIssue.cross_review_tags.map((tag: CrossReviewTag, idx: number) => ({
                    color: tag.tag === "CONFIRMED" ? "green" : tag.tag === "QUESTIONED" ? "red" : "orange",
                    children: (
                      <div>
                        <Space size={4}>
                          <Tag color={AGENT_COLOR[tag.reviewer_agent]}>{AGENT_LABEL[tag.reviewer_agent]}</Tag>
                          <Tag color={tag.tag === "CONFIRMED" ? "green" : tag.tag === "QUESTIONED" ? "red" : "orange"}>
                            {tag.tag === "CONFIRMED" ? "同意" : tag.tag === "QUESTIONED" ? "质疑" : "补充"}
                          </Tag>
                        </Space>
                        {tag.comment && <div className="text-xs mt-1">{tag.comment}</div>}
                      </div>
                    ),
                  }))}
                />
              </div>
            )}
          </div>
        )}
      </Drawer>
    </App>
  );
}
