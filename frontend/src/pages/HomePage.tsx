import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card, Tabs, Input, Button, Upload, Form, message, Typography, Space, Alert,
} from 'antd'
import { FileMarkdownOutlined, FilePdfOutlined, ApiOutlined, RocketOutlined, HistoryOutlined } from '@ant-design/icons'
import {
  startMarkdownReview, startFileReview, startTapdReview,
} from '../api/client'
import { useNavigate } from 'react-router-dom'

const { TextArea } = Input
const { Title, Text } = Typography

export default function HomePage() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [mdContent, setMdContent] = useState('')
  const handleSubmit = async (fn: () => Promise<string>) => {
    setLoading(true)
    try {
      const jobId = await fn()
      message.success(`审查任务已创建: ${jobId}`)
      navigate(`/report/${jobId}`)
    } catch (e: any) {
      message.error(`提交失败: ${e.message || e}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '40px 24px' }}>
      <div style={{ textAlign: 'center', marginBottom: 32 }}>
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
          <Button
            icon={<HistoryOutlined />}
            onClick={() => navigate('/history')}
          >
            审查历史
          </Button>
        </div>
        <Title level={2}>
          <RocketOutlined /> RevYou 需求文档审查系统
        </Title>
        <Text type="secondary">
          产品 / 开发 / 测试三个自主 Agent 并行交叉审查 · Plan → Execute → Reflect → Consolidate
        </Text>
      </div>

      <Card>
        <Tabs
          items={[
            {
              key: 'markdown',
              label: <span><FileMarkdownOutlined /> Markdown 粘贴</span>,
              children: (
                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                  <Alert
                    type="info"
                    message="粘贴需求文档的 Markdown 内容，或上传 .md 文件"
                    showIcon
                  />
                  <TextArea
                    rows={12}
                    value={mdContent}
                    onChange={(e) => setMdContent(e.target.value)}
                    placeholder="# 需求标题&#10;&#10;## 1. 背景&#10;...&#10;&#10;## 2. 功能需求&#10;..."
                  />
                  <Button
                    type="primary"
                    size="large"
                    block
                    loading={loading}
                    disabled={!mdContent.trim()}
                    onClick={() => handleSubmit(() => startMarkdownReview(mdContent))}
                  >
                    开始审查
                  </Button>
                </Space>
              ),
            },
            {
              key: 'file',
              label: <span><FilePdfOutlined /> 文件上传</span>,
              children: (
                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                  <Alert
                    type="info"
                    message="支持 .md 和 .pdf 格式的需求文档"
                    showIcon
                  />
                  <Upload.Dragger
                    accept=".md,.pdf"
                    maxCount={1}
                    showUploadList={true}
                    beforeUpload={(file) => {
                      handleSubmit(() => startFileReview(file))
                      return false
                    }}
                  >
                    <p className="ant-upload-drag-icon">
                      <FilePdfOutlined style={{ fontSize: 48, color: '#1677ff' }} />
                    </p>
                    <p className="ant-upload-text">点击或拖拽文件到此处</p>
                    <p className="ant-upload-hint">支持单个 .md 或 .pdf 文件</p>
                  </Upload.Dragger>
                </Space>
              ),
            },
            {
              key: 'tapd',
              label: <span><ApiOutlined /> TAPD 直连</span>,
              children: (
                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                  <Alert
                    type="info"
                    message="从 TAPD 拉取需求（需在服务端 .env 配置 TAPD_TOKEN）"
                    showIcon
                  />
                  <Form
                    layout="vertical"
                    onFinish={(values) =>
                      handleSubmit(() => startTapdReview(values.workspace, values.storyId))
                    }
                  >
                    <Form.Item
                      label="Workspace ID"
                      name="workspace"
                      rules={[{ required: true, message: '请输入 workspace ID' }]}
                    >
                      <Input placeholder="如 12345678" />
                    </Form.Item>
                    <Form.Item
                      label="需求 Story ID"
                      name="storyId"
                      rules={[{ required: true, message: '请输入需求 ID' }]}
                    >
                      <Input placeholder="如 112345678001234567" />
                    </Form.Item>
                    <Button type="primary" size="large" block htmlType="submit" loading={loading}>
                      从 TAPD 拉取并审查
                    </Button>
                  </Form>
                </Space>
              ),
            },
          ]}
        />
      </Card>
    </div>
  )
}
