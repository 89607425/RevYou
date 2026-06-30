"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter, useParams } from "next/navigation";
import { Button, Card, List, Typography, Space, Tag, Modal, Form, Input, Select, Radio, App, Tabs, Upload } from "antd";
import { PlusOutlined, ArrowLeftOutlined, FileTextOutlined, InboxOutlined } from "@ant-design/icons";
import type { UploadFile } from "antd";

const { Title, Text } = Typography;
const { TextArea } = Input;
const { Dragger } = Upload;

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
  const submittingRef = useRef(false);
  const [projectName, setProjectName] = useState("");
  const [activeMode, setActiveMode] = useState<string>("ALL");
  const [fileList, setFileList] = useState<UploadFile[]>([]);
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
    if (submittingRef.current) return;
    try {
      const values = await form.validateFields();
      submittingRef.current = true;
      setSubmitting(true);

      const token = localStorage.getItem("token");

      if (values.prd_source === "FILE") {
        if (fileList.length === 0) {
          message.error("请上传PRD文件");
          setSubmitting(false);
          return;
        }
        const formData = new FormData();
        formData.append("project_id", projectId);
        formData.append("agent_mode", values.agent_mode);
        formData.append("file", fileList[0] as any);

        const res = await fetch("http://localhost:8000/api/v1/sessions/upload", {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        });
        const data = await res.json();

        if (data.code === 0) {
          message.success("审查会话已创建，AI Agent 正在审查中...");
          setModalOpen(false);
          form.resetFields();
          setFileList([]);
          fetchSessions();
          router.push(`/sessions/${data.data.session_id}`);
        } else {
          message.error(data.detail || "创建失败");
        }
      } else {
        const body: any = {
          project_id: projectId,
          agent_mode: values.agent_mode,
          prd_source: values.prd_source,
        };

        if (values.prd_source === "TEXT") {
          body.prd_text = values.prd_text;
        } else if (values.prd_source === "TAPD") {
          body.tapd_story_id = values.tapd_story_id;
          body.tapd_workspace_id = values.tapd_workspace_id;
        }

        const res = await fetch("http://localhost:8000/api/v1/sessions", {
          method: "POST",
          headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const data = await res.json();

        if (data.code === 0) {
          const stats = data.data.tapd_import_stats;
          if (stats) {
            message.success(`审查会话已创建（已导入 TAPD 数据：${stats.tasks}个任务、${stats.bugs}个缺陷、${stats.comments}条评论、${stats.wikis}篇Wiki），AI Agent 正在审查中...`);
          } else {
            message.success("审查会话已创建，AI Agent 正在审查中...");
          }
          setModalOpen(false);
          form.resetFields();
          fetchSessions();
          router.push(`/sessions/${data.data.session_id}`);
        } else {
          message.error(data.detail || "创建失败");
        }
      }
    } catch (err: any) {
      if (err?.errorFields) {
        message.error("请填写所有必填项");
      } else {
        message.error("创建审查会话失败");
      }
    } finally {
      setSubmitting(false);
      submittingRef.current = false;
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
            <Space>
              <Button onClick={() => router.push(`/projects/${projectId}/settings`)}>项目设置</Button>
              <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
                新建审查
              </Button>
            </Space>
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
                      <Tag>{session.prd_source === "TAPD" ? "TAPD" : session.prd_source === "FILE" ? "文件" : "文本"}</Tag>
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
            onCancel={() => { setModalOpen(false); setFileList([]); }}
            onOk={handleCreate}
            confirmLoading={submitting}
            okButtonProps={{ loading: submitting, disabled: submitting }}
            width={640}
          >
            <Form form={form} layout="vertical" initialValues={{ agent_mode: "DETERMINISTIC", prd_source: "TEXT" }}>
              <Form.Item name="agent_mode" label="审查模式" rules={[{ required: true }]}>
                <Radio.Group>
                  <Radio.Button value="DETERMINISTIC">确定性工作流（一次性审查）</Radio.Button>
                  <Radio.Button value="AUTONOMOUS">自主Agent模式（支持追问）</Radio.Button>
                </Radio.Group>
              </Form.Item>

              <Form.Item name="prd_source" label="需求来源" rules={[{ required: true }]}>
                <Select>
                  <Select.Option value="TEXT">粘贴 PRD 文本</Select.Option>
                  <Select.Option value="FILE">上传 PDF/DOCX 文件</Select.Option>
                  <Select.Option value="TAPD">从 TAPD 导入</Select.Option>
                </Select>
              </Form.Item>

              <Form.Item noStyle shouldUpdate={(prev, cur) => prev.prd_source !== cur.prd_source}>
                {({ getFieldValue }) => {
                  const source = getFieldValue("prd_source");
                  if (source === "TEXT") {
                    return (
                      <Form.Item name="prd_text" label="PRD 内容" rules={[{ required: true, message: "请输入PRD内容" }]}>
                        <TextArea rows={10} placeholder="粘贴 PRD Markdown 文本内容..." showCount maxLength={50000} />
                      </Form.Item>
                    );
                  }
                  if (source === "FILE") {
                    return (
                      <Form.Item label="上传文件" rules={[{ required: true }]}>
                        <Dragger
                          accept=".pdf,.docx"
                          maxCount={1}
                          fileList={fileList}
                          onChange={({ fileList: fl }) => setFileList(fl)}
                          beforeUpload={() => false}
                        >
                          <p className="ant-upload-drag-icon"><InboxOutlined /></p>
                          <p className="ant-upload-text">点击或拖拽 PDF/DOCX 文件到此处</p>
                          <p className="ant-upload-hint">支持 .pdf 和 .docx 格式，最大 20MB</p>
                        </Dragger>
                      </Form.Item>
                    );
                  }
                  if (source === "TAPD") {
                    return (
                      <>
                        <Form.Item name="tapd_workspace_id" label="TAPD 项目 ID" rules={[{ required: true, message: "请输入TAPD项目ID" }]}
                          tooltip="TAPD 项目 URL 中 workspace_id 参数的值，如 https://www.tapd.cn/12345678 中的 12345678">
                          <Input placeholder="例如：12345678" />
                        </Form.Item>
                        <Form.Item name="tapd_story_id" label="TAPD 需求 ID" rules={[{ required: true, message: "请输入TAPD需求ID" }]}
                          tooltip="TAPD 需求的 19 位 ID，如 1012345678001234567">
                          <Input placeholder="例如：1012345678001234567" />
                        </Form.Item>
                        <Text type="secondary" style={{ display: "block", marginTop: -8, marginBottom: 16 }}>
                          将自动导入需求的描述、迭代、关联任务、缺陷、评论、Wiki 和变更历史
                        </Text>
                      </>
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
