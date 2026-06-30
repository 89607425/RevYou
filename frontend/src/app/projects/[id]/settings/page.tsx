"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { Button, Card, Typography, Space, Form, Input, Select, Switch, Slider, Divider, Descriptions, Alert, Spin, App } from "antd";
import { ArrowLeftOutlined, SaveOutlined, CheckCircleOutlined, ApiOutlined, RobotOutlined } from "@ant-design/icons";

const { Title, Text } = Typography;

export default function SettingsPage() {
  const router = useRouter();
  const params = useParams();
  const projectId = params.id as string;
  const { message } = App.useApp();

  const [project, setProject] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [validated, setValidated] = useState<any>(null);
  const [form] = Form.useForm();
  const [tapdForm] = Form.useForm();

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/login"); return; }
    fetchProject();
  }, [projectId]);

  const fetchProject = async () => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`http://localhost:8000/api/v1/projects/${projectId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (data.code === 0) {
        setProject(data.data);
        tapdForm.setFieldsValue({
          tapd_api_user: data.data.tapd_api_user || "",
        });
        form.setFieldsValue({
          pm_model: data.data.config?.pm_model || "glm-4",
          dev_model: data.data.config?.dev_model || "deepseek-v3",
          qa_model: data.data.config?.qa_model || "qwen-vl-max",
          multimodal_model: data.data.config?.multimodal_model || "glm-4v-plus",
          auto_switch_model: data.data.config?.auto_switch_model ?? true,
          confidence_threshold_low: data.data.config?.confidence_threshold_low ?? 0.5,
          confidence_threshold_high: data.data.config?.confidence_threshold_high ?? 0.8,
          max_review_rounds_deterministic: data.data.config?.max_review_rounds_deterministic ?? 1,
          max_review_rounds_autonomous: data.data.config?.max_review_rounds_autonomous ?? 3,
          max_follow_up_questions: data.data.config?.max_follow_up_questions ?? 5,
          session_timeout_deterministic_min: data.data.config?.session_timeout_deterministic_min ?? 5,
          session_timeout_autonomous_min: data.data.config?.session_timeout_autonomous_min ?? 10,
        });
      }
    } catch {
      message.error("获取项目信息失败");
    } finally {
      setLoading(false);
    }
  };

  const handleSaveConfig = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const token = localStorage.getItem("token");
      const res = await fetch(`http://localhost:8000/api/v1/projects/${projectId}/config`, {
        method: "PUT",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      const data = await res.json();
      if (data.code === 0) {
        message.success("配置已保存");
      } else {
        message.error(data.detail || "保存失败");
      }
    } catch {
      message.error("保存配置失败");
    } finally {
      setSaving(false);
    }
  };

  const handleValidateToken = async () => {
    try {
      const values = await tapdForm.validateFields();
      setValidating(true);
      setValidated(null);

      const token = localStorage.getItem("token");
      const res = await fetch(`http://localhost:8000/api/v1/tapd/validate?project_id=${projectId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (data.code === 0) {
        setValidated(data.data);
        if (data.data.valid) {
          message.success("TAPD 令牌有效！");
        } else {
          message.warning(data.data.message || "令牌验证失败");
        }
      } else {
        message.error(data.detail || "验证请求失败");
      }
    } catch {
      message.error("验证失败");
    } finally {
      setValidating(false);
    }
  };

  const handleSaveToken = async () => {
    try {
      const values = await tapdForm.validateFields();
      setSaving(true);
      const token = localStorage.getItem("token");
      const res = await fetch(`http://localhost:8000/api/v1/projects/${projectId}/tapd-token`, {
        method: "PUT",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ tapd_api_user: values.tapd_api_user, tapd_token: values.tapd_token }),
      });
      const data = await res.json();
      if (data.code === 0) {
        message.success("TAPD 令牌已保存");
        fetchProject();
      } else {
        message.error(data.detail || "保存失败");
      }
    } catch {
      message.error("保存令牌失败");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center min-h-screen"><Spin size="large" /></div>;
  }

  return (
      <div className="min-h-screen bg-gray-50">
        <div className="max-w-4xl mx-auto p-6">
          <div className="flex justify-between items-center mb-6">
            <Space>
              <Button icon={<ArrowLeftOutlined />} onClick={() => router.back()}>返回</Button>
              <Title level={4} style={{ margin: 0 }}>{project?.name} - 项目设置</Title>
            </Space>
          </div>

          <Card title={<Space><ApiOutlined /> TAPD 集成</Space>} className="mb-6">
            <Form form={tapdForm} layout="vertical">
              <Form.Item name="tapd_api_user" label="TAPD API User" rules={[{ required: true, message: "请输入TAPD API User" }]}
                tooltip="在 TAPD 个人设置 > API 中查看，通常为公司ID或用户名">
                <Input placeholder="输入 TAPD API User..." />
              </Form.Item>
              <Form.Item name="tapd_token" label="TAPD API Token（密码）" rules={[{ required: true, message: "请输入TAPD令牌" }]}
                tooltip="在 TAPD 个人设置 > API 中生成的 API Token，用作密码">
                <Input.Password placeholder="粘贴 TAPD API Token..." />
              </Form.Item>
              <Space>
                <Button onClick={handleValidateToken} loading={validating} icon={<CheckCircleOutlined />}>
                  验证令牌
                </Button>
                <Button type="primary" onClick={handleSaveToken} loading={saving} icon={<SaveOutlined />}>
                  保存令牌
                </Button>
              </Space>
            </Form>

            {validated && (
              <div className="mt-4">
                {validated.valid ? (
                  <Alert type="success" message={`令牌有效 - 可访问的工作空间: ${validated.workspaces?.map((w: any) => w.name).join(", ") || "N/A"}`}
                    showIcon />
                ) : (
                  <Alert type="error" message={validated.message || "令牌无效"} showIcon />
                )}
              </div>
            )}

            <Divider />
            <Descriptions title="当前状态" size="small" column={1}>
              <Descriptions.Item label="TAPD 项目 ID">{project?.tapd_project_id || "未关联"}</Descriptions.Item>
              <Descriptions.Item label="API User">
                {project?.tapd_api_user ? <Text type="success">{project.tapd_api_user}</Text> : <Text type="warning">未配置</Text>}
              </Descriptions.Item>
              <Descriptions.Item label="令牌状态">
                {project?.has_tapd_token ? <Text type="success">已配置</Text> : <Text type="warning">未配置</Text>}
              </Descriptions.Item>
            </Descriptions>
          </Card>

          <Card title={<Space><RobotOutlined /> Agent 审查配置</Space>} className="mb-6">
            <Form form={form} layout="vertical">
              <Divider orientation="left" plain>AI 模型</Divider>
              <Form.Item name="pm_model" label="PM 审查模型（产品视角）" tooltip="GLM-4 擅长中文理解，适合产品逻辑审查">
                <Select>
                  <Select.Option value="glm-4">GLM-4（智谱 · 推荐）</Select.Option>
                  <Select.Option value="deepseek-v3">DeepSeek-V3（DeepSeek）</Select.Option>
                  <Select.Option value="qwen-vl-max">Qwen-VL-Max（硅基流动）</Select.Option>
                  <Select.Option value="gemini-2.0-flash">Gemini 2.0 Flash（Google）</Select.Option>
                  <Select.Option value="gpt-4o">GPT-4o（硅基流动）</Select.Option>
                </Select>
              </Form.Item>

              <Form.Item name="dev_model" label="DEV 审查模型（技术视角）" tooltip="DeepSeek-V3 擅长逻辑推理，适合技术风险分析">
                <Select>
                  <Select.Option value="deepseek-v3">DeepSeek-V3（DeepSeek · 推荐）</Select.Option>
                  <Select.Option value="glm-4">GLM-4（智谱）</Select.Option>
                  <Select.Option value="qwen-vl-max">Qwen-VL-Max（硅基流动）</Select.Option>
                  <Select.Option value="gemini-2.0-flash">Gemini 2.0 Flash（Google）</Select.Option>
                  <Select.Option value="gpt-4o">GPT-4o（硅基流动）</Select.Option>
                </Select>
              </Form.Item>

              <Form.Item name="qa_model" label="QA 审查模型（测试视角）" tooltip="Qwen-VL-Max 多模态能力强，适合生成测试用例">
                <Select>
                  <Select.Option value="qwen-vl-max">Qwen-VL-Max（硅基流动 · 推荐）</Select.Option>
                  <Select.Option value="deepseek-v3">DeepSeek-V3（DeepSeek）</Select.Option>
                  <Select.Option value="glm-4">GLM-4（智谱）</Select.Option>
                  <Select.Option value="gemini-2.0-flash">Gemini 2.0 Flash（Google）</Select.Option>
                  <Select.Option value="gpt-4o">GPT-4o（硅基流动）</Select.Option>
                </Select>
              </Form.Item>

              <Form.Item name="auto_switch_model" label="自动切换多模态模型" valuePropName="checked"
                tooltip="检测到图片时自动切换为多模态模型">
                <Switch />
              </Form.Item>

              <Form.Item name="multimodal_model" label="多模态回退模型（含图片时切换）" tooltip="GLM-4V-Plus 支持视觉识别，适合分析PRD中的流程图和截图">
                <Select>
                  <Select.Option value="glm-4v-plus">GLM-4V-Plus（智谱 · 推荐）</Select.Option>
                  <Select.Option value="glm-4v-flash">GLM-4V-Flash（智谱 · 快速）</Select.Option>
                </Select>
              </Form.Item>

              <Divider orientation="left" plain>置信度阈值</Divider>
              <Form.Item name="confidence_threshold_low" label="低置信度阈值（低于此值折叠展示）">
                <Slider min={0} max={1} step={0.05} marks={{ 0: "0", 0.5: "0.5", 1: "1" }} />
              </Form.Item>
              <Form.Item name="confidence_threshold_high" label="高置信度阈值（高于此值标记高可信）">
                <Slider min={0} max={1} step={0.05} marks={{ 0: "0", 0.8: "0.8", 1: "1" }} />
              </Form.Item>

              <Divider orientation="left" plain>审查轮次与超时</Divider>
              <Form.Item name="max_review_rounds_deterministic" label="确定性模式最大审查轮次">
                <Slider min={1} max={5} marks={{ 1: "1", 3: "3", 5: "5" }} />
              </Form.Item>
              <Form.Item name="max_review_rounds_autonomous" label="自主模式最大审查轮次">
                <Slider min={1} max={5} marks={{ 1: "1", 3: "3", 5: "5" }} />
              </Form.Item>
              <Form.Item name="max_follow_up_questions" label="自主模式最大追问次数">
                <Slider min={0} max={10} marks={{ 0: "0", 5: "5", 10: "10" }} />
              </Form.Item>
              <Form.Item name="session_timeout_deterministic_min" label="确定性模式超时（分钟）">
                <Slider min={1} max={15} marks={{ 1: "1", 5: "5", 10: "10", 15: "15" }} />
              </Form.Item>
              <Form.Item name="session_timeout_autonomous_min" label="自主模式超时（分钟）">
                <Slider min={1} max={30} marks={{ 1: "1", 10: "10", 20: "20", 30: "30" }} />
              </Form.Item>

              <Button type="primary" onClick={handleSaveConfig} loading={saving} icon={<SaveOutlined />} size="large">
                保存配置
              </Button>
            </Form>
          </Card>
        </div>
    </div>
  );
}
