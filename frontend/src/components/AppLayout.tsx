"use client";

import { Layout, Menu, Button, Dropdown, Space, Avatar } from "antd";
import { useRouter, usePathname } from "next/navigation";
import {
  ProjectOutlined,
  DashboardOutlined,
  FileTextOutlined,
  LogoutOutlined,
  UserOutlined,
  SettingOutlined,
} from "@ant-design/icons";
import { useState, useEffect } from "react";
import { User } from "@/types";

const { Header, Sider, Content } = Layout;

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    const userStr = localStorage.getItem("user");
    if (userStr) {
      setUser(JSON.parse(userStr));
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    router.push("/login");
  };

  const menuItems = [
    { key: "/projects", icon: <ProjectOutlined />, label: "项目" },
    { key: "/dashboard", icon: <DashboardOutlined />, label: "仪表盘" },
  ];

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed}>
        <div className="h-16 flex items-center justify-center text-white text-lg font-bold">
          {collapsed ? "R" : "RevYou"}
        </div>
        <Menu
          theme="dark"
          selectedKeys={[pathname]}
          mode="inline"
          items={menuItems}
          onClick={({ key }) => router.push(key)}
        />
      </Sider>
      <Layout>
        <Header className="bg-white px-4 flex justify-end items-center border-b">
          <Space>
            <Dropdown
              menu={{
                items: [
                  { key: "settings", icon: <SettingOutlined />, label: "设置" },
                  { key: "logout", icon: <LogoutOutlined />, label: "退出", danger: true },
                ],
                onClick: ({ key }) => {
                  if (key === "logout") handleLogout();
                  if (key === "settings") router.push("/settings");
                },
              }}
            >
              <Space className="cursor-pointer">
                <Avatar icon={<UserOutlined />} />
                <span>{user?.display_name || "用户"}</span>
              </Space>
            </Dropdown>
          </Space>
        </Header>
        <Content className="m-4">{children}</Content>
      </Layout>
    </Layout>
  );
}
