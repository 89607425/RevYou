"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button, Card, List, Typography, Space, Tag, App } from "antd";
import { PlusOutlined, ProjectOutlined, LogoutOutlined } from "@ant-design/icons";

const { Title, Text } = Typography;

interface Project {
  project_id: string;
  name: string;
  tapd_project_id?: string;
  has_tapd_token: boolean;
  session_count: number;
  member_count: number;
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const { message } = App.useApp();

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/login");
      return;
    }
    fetchProjects();
  }, []);

  const fetchProjects = async () => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch("http://localhost:8000/api/v1/projects", {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (data.code === 0) {
        setProjects(data.data?.items || []);
      }
    } catch {
      message.error("获取项目列表失败");
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    router.push("/login");
  };

  return (
    <App>
      <div className="min-h-screen bg-gray-50">
        <div className="max-w-4xl mx-auto p-6">
          <div className="flex justify-between items-center mb-6">
            <Title level={3} style={{ margin: 0 }}>
              <ProjectOutlined className="mr-2" />
              我的项目
            </Title>
            <Space>
              <Button type="primary" icon={<PlusOutlined />} onClick={() => message.info("创建项目功能开发中")}>
                新建项目
              </Button>
              <Button icon={<LogoutOutlined />} onClick={handleLogout}>退出</Button>
            </Space>
          </div>

          <List
            loading={loading}
            dataSource={projects}
            renderItem={(project) => (
              <Card
                hoverable
                className="mb-3"
                onClick={() => router.push(`/projects/${project.project_id}/sessions`)}
              >
                <div className="flex justify-between items-center">
                  <div>
                    <Text strong style={{ fontSize: 16 }}>{project.name}</Text>
                    <div className="mt-1">
                      {project.has_tapd_token && <Tag color="blue">TAPD已集成</Tag>}
                      <Text type="secondary" className="text-sm">
                        审查会话: {project.session_count} | 成员: {project.member_count}
                      </Text>
                    </div>
                  </div>
                </div>
              </Card>
            )}
            locale={{ emptyText: "暂无项目" }}
          />
        </div>
      </div>
    </App>
  );
}
