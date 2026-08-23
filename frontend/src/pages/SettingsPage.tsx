import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card, Form, Input, Button, Typography, Space, Alert, message,
  InputNumber, Slider, Tag, Spin,
} from 'antd'
import {
  ArrowLeftOutlined, SettingOutlined, SafetyCertificateOutlined,
  ThunderboltOutlined, RobotOutlined,
} from '@ant-design/icons'
import {
  getLLMSettings, updateLLMSettings, testLLMConnection, LLMSettings,
} from '../api/client'

const { Title, Text } = Typography

/** Preset OpenAI-compatible providers */
const PRESETS: Record<string, { label: string; base_url: string; model: string }> = {
  deepseek: { label: 'DeepSeek', base_url: 'https://api.deepseek.com/v1', model: 'deepseek-chat' },
  openai: { label: 'OpenAI', base_url: 'https://api.openai.com/v1', model: 'gpt-4o' },
  moonshot: { label: 'Kimi (Moonshot)', base_url: 'https://api.moonshot.cn/v1', model: 'moonshot-v1-128k' },
  zhipu: { label: '智谱 GLM', base_url: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4.5' },
  qwen: { label: '通义千问', base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-plus' },
  siliconflow: { label: 'SiliconFlow', base_url: 'https://api.siliconflow.cn/v1', model: 'Qwen/Qwen2.5-72B-Instruct' },
}

interface FormValues {
  base_url: string
  api_key?: string
  model: string
  temperature: number
  max_tokens: number
}

export default function SettingsPage() {
  const navigate = useNavigate()
  const [form] = Form.useForm<FormValues>()
  const [current, setCurrent] = useState<LLMSettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; text: string } | null>(null)

  const load = async () => {
    try {
      const s = await getLLMSettings()
      setCurrent(s)
      form.setFieldsValue({
        base_url: s.base_url,
        model: s.model,
        temperature: s.temperature,
        max_tokens: s.max_tokens,
        api_key: undefined,
      })
    } catch (e: any) {
      message.error(`加载配置失败: ${e.message || e}`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const applyPreset = (key: string) => {
    const p = PRESETS[key]
    if (!p) return
    form.setFieldsValue({ base_url: p.base_url, model: p.model })
    message.info(`已填入 ${p.label} 预设，请补全 API Key`)
  }

  const handleSave = async (values: FormValues) => {
    setSaving(true)
    try {
      const payload: Record<string, unknown> = {
        base_url: values.base_url,
        model: values.model,
        temperature: values.temperature,
        max_tokens: values.max_tokens,
      }
      // Only send the key when the user typed a new one
      if (values.api_key && values.api_key.trim()) {
        payload.api_key = values.api_key.trim()
      }
      const s = await updateLLMSettings(payload)
      setCurrent(s)
      form.setFieldValue('api_key', undefined)
      message.success('配置已保存并即时生效')
    } catch (e: any) {
      message.error(`保存失败: ${e.message || e}`)
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    const values = await form.validateFields(['base_url', 'model'])
    setTesting(true)
    setTestResult(null)
    try {
      const result = await testLLMConnection({
        base_url: values.base_url,
        model: values.model,
        api_key: form.getFieldValue('api_key')?.trim() || undefined,
      })
      setTestResult({
        ok: true,
        text: `连接成功 · 模型 ${result.model} · 延迟 ${result.latency_ms}ms · 回复 "${result.reply}"`,
      })
    } catch (e: any) {
      setTestResult({ ok: false, text: `${e.message || e}` })
    } finally {
      setTesting(false)
    }
  }

  const detectPreset = (baseUrl: string): string | null => {
    for (const [key, p] of Object.entries(PRESETS)) {
      if (baseUrl.startsWith(p.base_url.replace(/\/v\d.*$/, ''))) return key
    }
    return null
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 80 }}>
        <Spin size="large" />
      </div>
    )
  }

  const activePreset = current ? detectPreset(current.base_url) : null

  return (
    <div style={{ maxWidth: 760, margin: '0 auto', padding: '40px 24px' }}>
      <div style={{ marginBottom: 24 }}>
        <Button icon={<ArrowLeftOutlined />} type="text" onClick={() => navigate('/')}>
          返回首页
        </Button>
      </div>

      <Title level={2} style={{ textAlign: 'center', marginBottom: 4 }}>
        <SettingOutlined /> LLM 配置
      </Title>
      <Text type="secondary" style={{ display: 'block', textAlign: 'center', marginBottom: 32 }}>
        配置大语言模型的服务地址、密钥与模型，保存后立即生效并持久化到服务端 .env
      </Text>

      <Alert
        type="info"
        showIcon
        icon={<RobotOutlined />}
        style={{ marginBottom: 24 }}
        message="支持任意 OpenAI 兼容接口"
        description="RevYou 的三个审查 Agent 通过 OpenAI 兼容协议调用 LLM，可自由切换 DeepSeek、OpenAI、Kimi、智谱、通义千问等厂商。"
      />

      <Card>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          {current && (
            <div>
              <Text strong>当前生效配置：</Text>{' '}
              <Tag color={activePreset ? 'blue' : 'default'}>
                {activePreset ? PRESETS[activePreset].label : '自定义'}
              </Tag>
              <Tag icon={<RobotOutlined />} color="geekblue">{current.model}</Tag>
              <Tag color={current.api_key_set ? 'green' : 'red'}>
                <SafetyCertificateOutlined /> API Key {current.api_key_set ? `已配置（${current.api_key_masked}）` : '未配置'}
              </Tag>
            </div>
          )}

          <div>
            <Text strong style={{ display: 'block', marginBottom: 12 }}>快速预设</Text>
            <Space wrap>
              {Object.entries(PRESETS).map(([key, p]) => (
                <Button key={key} onClick={() => applyPreset(key)}>{p.label}</Button>
              ))}
            </Space>
          </div>

          <Form
            form={form}
            layout="vertical"
            onFinish={handleSave}
            initialValues={{ temperature: 0.2, max_tokens: 8192 }}
          >
            <Form.Item
              label="API Base URL"
              name="base_url"
              rules={[
                { required: true, message: '请输入 API Base URL' },
                { type: 'url', message: '请输入合法的 URL（含 https://）' },
              ]}
              extra="OpenAI 兼容接口地址，如 https://api.deepseek.com/v1"
            >
              <Input placeholder="https://api.deepseek.com/v1" />
            </Form.Item>

            <Form.Item
              label="API Key"
              name="api_key"
              extra={
                current?.api_key_set
                  ? `已有 Key：${current.api_key_masked}，留空表示沿用当前 Key`
                  : '尚未配置 Key，请输入'
              }
            >
              <Input.Password
                placeholder={current?.api_key_set ? '留空则沿用当前已保存的 Key' : 'sk-...'}
                autoComplete="new-password"
              />
            </Form.Item>

            <Form.Item
              label="模型名称"
              name="model"
              rules={[{ required: true, message: '请输入模型名称' }]}
              extra="如 deepseek-chat、gpt-4o、glm-4.5 等"
            >
              <Input placeholder="deepseek-chat" />
            </Form.Item>

            <Form.Item label="Temperature（创造性）" name="temperature">
              <Slider min={0} max={1} step={0.05} marks={{ 0: '0 严谨', 0.2: '0.2', 0.5: '0.5', 1: '1 发散' }} />
            </Form.Item>

            <Form.Item
              label="Max Tokens（单次回复上限）"
              name="max_tokens"
              rules={[{ required: true, message: '请输入 max_tokens' }]}
            >
              <InputNumber min={256} max={131072} step={256} style={{ width: '100%' }} />
            </Form.Item>

            {testResult && (
              <Alert
                type={testResult.ok ? 'success' : 'error'}
                showIcon
                message={testResult.ok ? '连通性测试通过' : '连通性测试失败'}
                description={testResult.text}
                style={{ marginBottom: 24 }}
              />
            )}

            <Space style={{ width: '100%', justifyContent: 'space-between' }}>
              <Button
                icon={<ThunderboltOutlined />}
                loading={testing}
                onClick={handleTest}
              >
                测试连接
              </Button>
              <Button type="primary" size="large" htmlType="submit" loading={saving}>
                保存配置
              </Button>
            </Space>
          </Form>
        </Space>
      </Card>
    </div>
  )
}
