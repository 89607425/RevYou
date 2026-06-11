"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { Layout, Button, Typography, Space, Tag, Spin, Tabs, Card, Empty, message, Input, Modal, App } from "antd";
import { ArrowLeftOutlined, StopOutlined, ReloadOutlined, ExportOutlined, CopyOutlined } from "@ant-design/icons";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const { Sider, Content } = Layout;
const { Title, Text } = Typography;
const { TextArea } = Input;

interface ReviewIssue {
  issue_id: string;
  source_agent: string;
  severity: string;
  title: string;
  description: string;
  suggestion?: string;
  prd_section?: string;
  confidence: number;
  confidence_label: string;
  status: string;
}

interface FollowUp {
  follow_up_id: string;
  source_agent: string;
  question: string;
  status: string;
  answer?: string;
}

export default function ReviewWorkspacePage() {
  const router = useRouter();
  const params = useParams();
  const sessionId = params.id as string;
  const { message: msg } = App.useApp();

  const [session, setSession] = useState<any>(null);
  const [issues, setIssues] = useState<ReviewIssue[]>([]);
  const [followUps, setFollowUps] = useState<FollowUp[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeIssueTab, setActiveIssueTab] = useState("ALL");
  const [replyModal, setReplyModal] = useState<{ open: boolean; followUpId: string; question: string }>({
    open: false,
    followUpId: "",
    question: "",
  });
  const [replyText, setReplyText] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }
    fetchSession();
  }, [sessionId]);

  const fetchSession = async () => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`http://localhost:8000/api/v1/sessions/${sessionId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (data.code === 0) {
        setSession(data.data);
        fetchIssues();
        setFollowUps(data.data.follow_up_questions || []);
      }
    } catch (error) {
      msg.error("获取审查会话失败");
    } finally {
      setLoading(false);
    }
  };

  const fetchIssues = async (agent?: string) => {
    try {
      const token = localStorage.getItem("token");
      const agentParam = agent && agent !== "ALL" ? `&source_agent=${agent}` : "";
      const res = await fetch(
        `http://localhost:8000/api/v1/sessions/${sessionId}/issues?page=1&page_size=100${agentParam}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const data = await res.json();
      if (data.code === 0) {
        setIssues(data.data?.items || []);
      }
    } catch {}
  };

  const handleIssueAction = async (issueId: string, status: string, note?: string) => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`http://localhost:8000/api/v1/sessions/${sessionId}/issues/${issueId}`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ status, resolution_note: note }),
      });
      const data = await res.json();
      if (data.code === 0) {
        msg.success("操作成功");
        fetchIssues(activeIssueTab);
      }
    } catch {
      msg.error("操作失败");
    }
  };

  const handleCopyIssue = async (issueId: string) => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`http://localhost:8000/api/v1/sessions/${sessionId}/issues/${issueId}/copy`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (data.code === 0) {
        await navigator.clipboard.writeText(data.data.copy_text);
        msg.success("已复制到剪贴板");
      }
    } catch {
      msg.error("复制失败");
    }
  };

  const handleFollowUpReply = async (followUpId: string) => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`http://localhost:8000/api/v1/sessions/${sessionId}/follow-ups/${followUpId}/answer`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ action: "ANSWER", answer: replyText }),
      });
      const data = await res.json();
      if (data.code === 0) {
        msg.success("已回答追问");
        setReplyModal({ open: false, followUpId: "", question: "" });
        setReplyText("");
      }
    } catch {
      msg.error("回复失败");
    }
  };

  const handleFollowUpSkip = async (followUpId: string) => {
    try {
      const token = localStorage.getItem("token");
      await fetch(`http://localhost:8000/api/v1/sessions/${sessionId}/follow-ups/${followUpId}/answer`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ action: "SKIP" }),
      });
      msg.success("已跳过追问");
    } catch {
      msg.error("操作失败");
    }
  };

  const handleCancel = async () => {
    try {
      const token = localStorage.getItem("token");
      await fetch(`http://localhost:8000/api/v1/sessions/${sessionId}/cancel`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      msg.success("审查已终止");
      fetchSession();
    } catch {
      msg.error("操作失败");
    }
  };

  const severityColor: Record<string, string> = { HIGH: "red", MEDIUM: "orange", LOW: "blue" };
  const agentLabel: Record<string, string> = {
    PM_REVIEW: "PM",
    DEV_REVIEW: "Dev",
    QA_REVIEW: "QA",
  };

  const filteredIssues = activeIssueTab === "ALL"
    ? issues
    : issues.filter((i) => i.source_agent === activeIssueTab);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Spin size="large" />
      </div>
    );
  }

  return (
    <App>
      <Layout style={{ minHeight: "100vh", background: "#fff" }}>
        {/* Top Nav */}
        <div className="h-14 bg-white border-b flex items-center justify-between px-4">
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={() => router.back()}>返回</Button>
            <Title level={5} style={{ margin: 0 }}>{sessionId}</Title>
            {session && (
              <Tag color={session.status === "COMPLETED" ? "success" : session.status === "RUNNING" ? "processing" : "default"}>
                {session.status === "RUNNING" ? "审查中" : session.status === "COMPLETED" ? "已完成" : session.status}
              </Tag>
            )}
          </Space>
          <Space>
            {session?.status === "RUNNING" && (
              <Button danger icon={<StopOutlined />} onClick={handleCancel}>终止审查</Button>
            )}
            <Button icon={<ReloadOutlined />} disabled={session?.status === "RUNNING"}>重新审查</Button>
            <Button icon={<ExportOutlined />}>导出报告</Button>
          </Space>
        </div>

        <Layout>
          {/* Left - PRD Structure */}
          <Sider width={240} style={{ background: "#fafafa", padding: 16, overflow: "auto" }}>
            <Title level={5}>PRD 目录</Title>
            {session?.prd_structure?.sections?.length > 0 ? (
              session.prd_structure.sections.map((s: any) => (
                <div key={s.section_id} className="py-1 cursor-pointer hover:text-blue-500" style={{ paddingLeft: (s.level - 1) * 16 }}>
                  <Text>{s.title}</Text>
                </div>
              ))
            ) : (
              <Empty description="无章节结构" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
            <div className="mt-6">
              <Title level={5}>Agent 状态</Title>
              {["PM_REVIEW", "DEV_REVIEW", "QA_REVIEW"].map((agent) => (
                <div key={agent} className="flex items-center gap-2 py-1">
                  <Tag>{agentLabel[agent]}</Tag>
                  <Text type="secondary" className="text-xs">
                    {session?.status === "RUNNING" ? "⏳" : "✅"}
                    {issues.filter((i) => i.source_agent === agent).length} 个问题
                  </Text>
                </div>
              ))}
            </div>
          </Sider>

          {/* Center - PRD Content */}
          <Content style={{ padding: 24, overflow: "auto", background: "#fff" }}>
            <div className="prose max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {session?.prd_content || "暂无PRD内容"}
              </ReactMarkdown>
            </div>
          </Content>

          {/* Right - Issues & Follow-ups */}
          <Sider width={400} style={{ background: "#fafafa", padding: 16, overflow: "auto" }}>
            {/* Follow-up Questions */}
            {followUps.filter((f) => f.status === "PENDING").length > 0 && (
              <div className="mb-4">
                <Title level={5} className="text-red-500">
                  追问 ({followUps.filter((f) => f.status === "PENDING").length})
                </Title>
                {followUps.filter((f) => f.status === "PENDING").map((fu) => (
                  <Card key={fu.follow_up_id} size="small" className="mb-2 border-orange-300">
                    <Tag>{agentLabel[fu.source_agent]}</Tag>
                    <Text className="block my-1">{fu.question}</Text>
                    <Space className="mt-2">
                      <Button
                        size="small"
                        type="primary"
                        onClick={() => setReplyModal({ open: true, followUpId: fu.follow_up_id, question: fu.question })}
                      >
                        回复
                      </Button>
                      <Button size="small" onClick={() => handleFollowUpSkip(fu.follow_up_id)}>跳过</Button>
                    </Space>
                  </Card>
                ))}
              </div>
            )}

            {/* Issues */}
            <Title level={5}>问题列表 ({filteredIssues.length})</Title>
            <Tabs
              activeKey={activeIssueTab}
              onChange={(key) => { setActiveIssueTab(key); fetchIssues(key); }}
              size="small"
              items={[
                { key: "ALL", label: "全部" },
                { key: "PM_REVIEW", label: "PM" },
                { key: "DEV_REVIEW", label: "Dev" },
                { key: "QA_REVIEW", label: "QA" },
              ]}
            />

            <div className="overflow-auto" style={{ maxHeight: "calc(100vh - 300px)" }}>
              {filteredIssues.length === 0 ? (
                <Empty description="暂无问题" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              ) : (
                filteredIssues.map((issue) => (
                  <Card
                    key={issue.issue_id}
                    size="small"
                    className="mb-2"
                    title={
                      <Space size={4}>
                        <Tag color={severityColor[issue.severity]}>{issue.severity}</Tag>
                        <Tag>{agentLabel[issue.source_agent]}</Tag>
                        <Text className="text-xs">{issue.title}</Text>
                      </Space>
                    }
                  >
                    <Text className="text-xs" type="secondary">{issue.description}</Text>
                    {issue.suggestion && (
                      <div className="mt-2 p-2 bg-blue-50 rounded text-xs">
                        <Text strong>建议：</Text>{issue.suggestion}
                      </div>
                    )}
                    <div className="mt-2 flex justify-between items-center">
                      <Text className="text-xs" type="secondary">
                        置信度: {issue.confidence}
                      </Text>
                      <Space size={4}>
                        <Button size="small" icon={<CopyOutlined />} onClick={() => handleCopyIssue(issue.issue_id)} />
                        <Button size="small" type="primary" onClick={() => handleIssueAction(issue.issue_id, "CONFIRMED")}>
                          确认
                        </Button>
                        <Button
                          size="small"
                          danger
                          onClick={() => {
                            const note = prompt("请输入误报原因:");
                            if (note) handleIssueAction(issue.issue_id, "FALSE_POSITIVE", note);
                          }}
                        >
                          误报
                        </Button>
                      </Space>
                    </div>
                  </Card>
                ))
              )}
            </div>
          </Sider>
        </Layout>
      </Layout>

      <Modal
        title="回复追问"
        open={replyModal.open}
        onCancel={() => setReplyModal({ open: false, followUpId: "", question: "" })}
        onOk={() => handleFollowUpReply(replyModal.followUpId)}
      >
        <Text className="block mb-3">{replyModal.question}</Text>
        <TextArea rows={4} value={replyText} onChange={(e) => setReplyText(e.target.value)} placeholder="输入您的回复..." />
      </Modal>
    </App>
  );
}
