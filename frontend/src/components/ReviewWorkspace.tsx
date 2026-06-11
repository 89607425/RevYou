"use client";

import { Layout, Spin, Typography, Empty } from "antd";
import { LoadingOutlined } from "@ant-design/icons";

const { Sider, Content } = Layout;
const { Title, Text } = Typography;

export default function ReviewWorkspace() {
  return (
    <Layout style={{ minHeight: "calc(100vh - 120px)", background: "#fff" }}>
      <Sider width={240} style={{ background: "#fafafa", padding: 16 }}>
        <Title level={5}>PRD 目录</Title>
        <Empty description="加载中..." image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Sider>
      <Content style={{ padding: 24 }}>
        <div className="flex items-center justify-center h-full">
          <Spin indicator={<LoadingOutlined />} tip="正在加载审查内容...">
            <div style={{ padding: 50 }} />
          </Spin>
        </div>
      </Content>
      <Sider width={380} style={{ background: "#fafafa", padding: 16 }}>
        <Title level={5}>问题列表</Title>
        <Empty description="等待审查结果..." image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Sider>
    </Layout>
  );
}
