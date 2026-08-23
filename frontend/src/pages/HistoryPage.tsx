import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card, Table, Button, Input, Space, Tag, Typography, message, Popconfirm,
  Select, Empty, Spin,
} from 'antd'
import {
  ArrowLeftOutlined, DeleteOutlined, EyeOutlined,
  SearchOutlined, FileMarkdownOutlined, FilePdfOutlined, ApiOutlined,
} from '@ant-design/icons'
import {
  listJobs, deleteJob,
  type JobListItem,
  SOURCE_TYPE_LABELS, STATUS_META,
} from '../api/client'

const { Title, Text } = Typography

const SOURCE_ICONS: Record<string, React.ReactNode> = {
  markdown: <FileMarkdownOutlined />,
  pdf: <FilePdfOutlined />,
  tapd: <ApiOutlined />,
}

export default function HistoryPage() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [jobs, setJobs] = useState<JobListItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [keyword, setKeyword] = useState('')
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [sourceFilter, setSourceFilter] = useState<string | undefined>()

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const resp = await listJobs({
        limit: pageSize,
        offset: (page - 1) * pageSize,
        keyword: keyword || undefined,
        status: statusFilter,
        source_type: sourceFilter,
      })
      setJobs(resp.items)
      setTotal(resp.total)
    } catch (e: any) {
      message.error(`加载失败: ${e.message || e}`)
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, keyword, statusFilter, sourceFilter])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleDelete = async (jobId: string) => {
    try {
      await deleteJob(jobId)
      message.success('已删除')
      fetchData()
    } catch (e: any) {
      message.error(`删除失败: ${e.message || e}`)
    }
  }

  const columns = [
    {
      title: '文档标题',
      dataIndex: 'document_title',
      key: 'document_title',
      ellipsis: true,
      render: (text: string | null, record: JobListItem) => (
        <Space>
          {SOURCE_ICONS[record.source_type]}
          <span>{text || record.source_ref || record.id}</span>
        </Space>
      ),
    },
    {
      title: '来源',
      dataIndex: 'source_type',
      key: 'source_type',
      width: 100,
      render: (v: string) => SOURCE_TYPE_LABELS[v] || v,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (v: string) => {
        const meta = STATUS_META[v] || { label: v, color: 'default' }
        return <Tag color={meta.color}>{meta.label}</Tag>
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (v: string) => {
        if (!v) return '-'
        try {
          const d = new Date(v)
          return d.toLocaleString('zh-CN')
        } catch {
          return v
        }
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_: any, record: JobListItem) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            disabled={!record.has_report && record.status !== 'failed'}
            onClick={() => navigate(`/report/${record.id}`)}
          >
            查看
          </Button>
          <Popconfirm
            title="确认删除？"
            description="删除后无法恢复，该审查的所有思考轨迹也将被清除。"
            onConfirm={() => handleDelete(record.id)}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button
              type="link"
              size="small"
              danger
              icon={<DeleteOutlined />}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '24px' }}>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/')}>
          返回
        </Button>
        <Title level={4} style={{ margin: 0 }}>
          审查历史
        </Title>
      </Space>

      <Card>
        <div style={{ marginBottom: 16, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <Input
            placeholder="搜索文档标题或来源"
            prefix={<SearchOutlined />}
            allowClear
            style={{ width: 260 }}
            value={keyword}
            onChange={(e) => {
              setKeyword(e.target.value)
              setPage(1)
            }}
          />
          <Select
            placeholder="状态筛选"
            allowClear
            style={{ width: 140 }}
            value={statusFilter}
            onChange={(v) => { setStatusFilter(v); setPage(1) }}
            options={Object.entries(STATUS_META).map(([k, v]) => ({
              value: k, label: v.label,
            }))}
          />
          <Select
            placeholder="来源筛选"
            allowClear
            style={{ width: 140 }}
            value={sourceFilter}
            onChange={(v) => { setSourceFilter(v); setPage(1) }}
            options={Object.entries(SOURCE_TYPE_LABELS).map(([k, v]) => ({
              value: k, label: v,
            }))}
          />
        </div>

        <Table
          rowKey="id"
          columns={columns}
          dataSource={jobs}
          loading={loading}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
            onChange: (p, ps) => { setPage(p); setPageSize(ps) },
          }}
          locale={{
            emptyText: loading ? <Spin /> : <Empty description="暂无审查记录" />,
          }}
          size="middle"
        />
      </Card>
    </div>
  )
}
