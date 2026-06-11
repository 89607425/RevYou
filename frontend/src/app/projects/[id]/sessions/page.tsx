"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { Button, Card, List, Typography, Space, Tag, Modal, Form, Input, Select, Radio, App, Tabs } from "antd";
import { PlusOutlined, ArrowLeftOutlined, FileTextOutlined } from "@ant-design/icons";

const { Title, Text } = Typography;
const { TextArea } = Input;

interface Session {
  session_id: string;
  project_id: string;
  status: string;
  agent_mode: string;
  prd_source: string;
  issue_count: { HIGH: number; MEDIUM: number; LOW: number; total: number };
  initiator: { user_id: string; display_name: string };
  created_at: string;
  completed_at: string | null;
}

export default function SessionsPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params.id as string;
  const { message } = App.useApp();

  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [projectName, setProjectName] = useState("");
  const [activeMode, setActiveMode] = useState<string>("ALL");
  const [form] = Form.useForm();

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }
    fetchProject();
    fetchSessions();
  }, [projectId, activeMode]);

  const fetchProject = async () => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`http://localhost:8000/api/v1/projects/${projectId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (data.code === 0) {
        setProjectName(data.data.name);
      }
    } catch {}
  };

  const fetchSessions = async () => {
    try {
      const token = localStorage.getItem("token");
      const statusParam = activeMode !== "ALL" ? `&status=${activeMode}` : "";
      const res = await fetch(`http://localhost:8000/api/v1/sessions?project_id=${projectId}${statusParam}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (data.code === 0) {
        setSessions(data.data?.items || []);
      }
    } catch {
      message.error("获取审查列表失败");
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);

      const token = localStorage.getItem("token");
      const params = new URLSearchParams();
      params.append("project_id", projectId);
      params.append("agent_mode", values.agent_mode);
      params.append("prd_source", values.prd_source);
      if (values.prd_source === "TEXT") {
        params.append("prd_text", values.prd_text);
      }
      if (values.tapd_story_id) {
        params.append("tapd_story_id", values.tapd_story_id);
      }

      const res = await fetch(`http://localhost:8000/api/v1/sessions?${params.toString()}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });

      const data = await res.json();
      if (data.code === 0) {
        message.success("审查会话已创建");
        setModalOpen(false);
        form.resetFields();
        fetchSessions();
        router.push(`/sessions/${data.data.session_id}`);
      } else {
        message.error("创建失败");
      }
    } catch {
      message.error("创建审查会话失败");
    } finally {
      setSubmitting(false);
    }
  };

  const statusColor: Record<string, string> = {
    RUNNING: "processing",
    COMPLETED: "success",
    TIMEOUT: "warning",
    CANCELLED: "default",
  };

  const statusText: Record<string, string> = {
    RUNNING: "审查中",
    COMPLETED: "已完成",
    TIMEOUT: "已超时",
    CANCELLED: "已取消",
  };

  return (
    <App>
      <div className="min-h-screen bg-gray-50">
        <div className="max-w-5xl mx-auto p-6">
          <div className="flex justify-between items-center mb-6">
            <Space>
              <Button icon={<ArrowLeftOutlined />} onClick={() => router.push("/projects")}>返回</Button>
              <Title level={4} style={{ margin: 0 }}>{projectName} - 审查会话</Title>
            </Space>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
              新建审查
            </Button>
          </div>

          <Tabs
            activeKey={activeMode}
            onChange={setActiveMode}
            items={[
              { key: "ALL", label: "全部" },
              { key: "RUNNING", label: "审查中" },
              { key: "COMPLETED", label: "已完成" },
              { key: "TIMEOUT", label: "已超时" },
            ]}
          />

          <List
            loading={loading}
            dataSource={sessions}
            renderItem={(session) => (
              <Card
                hoverable
                className="mb-3"
                onClick={() => router.push(`/sessions/${session.session_id}`)}
              >
                <div className="flex justify-between items-center">
                  <Space direction="vertical" size={2}>
                    <Space>
                      <FileTextOutlined />
                      <Text strong>{session.session_id}</Text>
                      <Tag color={statusColor[session.status]}>{statusText[session.status]}</Tag>
                      <Tag>{session.agent_mode === "AUTONOMOUS" ? "自主模式" : "确定性模式"}</Tag>
                    </Space>
                    <Text type="secondary" className="text-xs">
                      发起人: {session.initiator?.display_name} | {session.created_at}
                    </Text>
                  </Space>
                  {session.issue_count.total > 0 && (
                    <Space>
                      <Tag color="red">高 {session.issue_count.HIGH}</Tag>
                      <Tag color="orange">中 {session.issue_count.MEDIUM}</Tag>
                      <Tag color="blue">低 {session.issue_count.LOW}</Tag>
                    </Space>
                  )}
                </div>
              </Card>
            )}
            locale={{ emptyText: "暂无审查会话" }}
          />

          <Modal
            title="新建审查会话"
            open={modalOpen}
            onCancel={() => setModalOpen(false)}
            onOk={handleCreate}
            confirmLoading={submitting}
            width={600}
          >
            <Form form={form} layout="vertical" initialValues={{ agent_mode: "DETERMINISTIC", prd_source: "TEXT" }}>
              <Form.Item name="agent_mode" label="审查模式" rules={[{ required: true }]}>
                <Radio.Group>
                  <Radio.Button value="DETERMINISTIC">确定性工作流</Radio.Button>
                  <Radio.Button value="AUTONOMOUS">自主Agent模式</Radio.Button>
                </Radio.Group>
              </Form.Item>
              <Form.Item name="prd_source" label="需求来源" rules={[{ required: true }]}>
                <Select>
                  <Select.Option value="TEXT">粘贴文本</Select.Option>
                  <Select.Option value="FILE">上传文件</Select.Option>
                  <Select.Option value="TAPD">TAPD需求单</Select.Option>
                </Select>
              </Form.Item>
              <Form.Item noStyle shouldUpdate={(prev, cur) => prev.prd_source !== cur.prd_source}>
                {({ getFieldValue }) => {
                  const source = getFieldValue("prd_source");
                  if (source === "TEXT") {
                    return (
                      <Form.Item name="prd_text" label="PRD内容" rules={[{ required: true, message: "请输入PRD内容" }]}>
                        <TextArea rows={8} placeholder="粘贴PRD文本内容..." />
                      </Form.Item>
                    );
                  }
                  if (source === "TAPD") {
                    return (
                      <Form.Item name="tapd_story_id" label="TAPD需求ID" rules={[{ required: true }]}>
                        <Input placeholder="输入TAPD Story ID" />
                      </Form.Item>
                    );
                  }
                  return null;
                }}
              </Form.Item>
            </Form>
          </Modal>
        </div>
      </div>
    </App>
  );
}
