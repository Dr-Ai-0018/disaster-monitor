# Disaster Monitor Workflow Frontend

企业级灾害监测工作流前端系统 - React + TypeScript + TailwindCSS + shadcn/ui

## 技术栈

- **框架**: React 18 + TypeScript
- **构建工具**: Vite
- **样式**: TailwindCSS + shadcn/ui 组件
- **路由**: React Router v6
- **HTTP 客户端**: Axios 1.14.0
- **图标**: Lucide React
- **日期处理**: date-fns
- **图表**: Recharts

## 功能特性

### 五池工作流管理
- **事件池**: 自动抓取和管理灾害事件
- **影像池**: 自动 GEE 影像下载
- **影像审核池**: 人工/AI 影像质量审核
- **推理池**: Latest Model API 推理触发和监控
- **摘要日报池**: 摘要生成、审核和日报管理

### 核心页面
- **登录页**: JWT 认证
- **仪表盘**: 五池总览、实时统计
- **工作流池**: 多池切换、批量操作、详细状态
- **事件详情**: 完整事件信息、工作流操作
- **日报管理**: 生成、预览、发布日报
- **日报详情**: 日报内容查看和统计

### 批量操作
- 批量影像审核（通过/打回）
- 批量触发推理
- 批量生成摘要
- 批量准入日报候选

## 开发

```bash
# 安装依赖
npm install

# 启动开发服务器（需要后端运行在 2335 端口）
npm run dev

# 类型检查
npm run build
```

开发服务器会在 http://localhost:5173 启动，并自动代理 `/api` 到后端服务器。

## 构建

```bash
# 生产构建
npm run build

# 构建输出在 dist/ 目录
```

构建后的文件会被后端 FastAPI 服务器自动提供服务。

## 项目结构

```
src/
├── components/          # 可复用组件
│   ├── ui/             # shadcn/ui 基础组件
│   └── Layout.tsx      # 应用布局
├── pages/              # 页面组件
│   ├── Login.tsx       # 登录页
│   ├── Dashboard.tsx   # 仪表盘
│   ├── Pools.tsx       # 工作流池管理
│   ├── ItemDetail.tsx  # 事件详情
│   ├── Reports.tsx     # 日报列表
│   └── ReportDetail.tsx # 日报详情
├── lib/                # 工具库
│   ├── api.ts          # API 客户端
│   └── utils.ts        # 工具函数
├── types/              # TypeScript 类型定义
│   └── index.ts
├── App.tsx             # 路由配置
└── main.tsx            # 入口文件
```

## API 集成

所有 API 请求通过 `src/lib/api.ts` 统一管理：

- **认证 API**: 登录、刷新令牌
- **工作流 API**: 五池数据、批量操作、状态管理
- **日报 API**: 候选管理、日报生成和发布

自动处理：
- JWT Token 注入
- 401 自动跳转登录
- 统一错误处理

## 环境要求

- Node.js >= 18
- npm >= 9

## 部署

前端构建后集成到后端服务器，无需单独部署：

1. 构建前端: `npm run build`
2. 启动后端: `cd .. && python main.py`
3. 访问: http://127.0.0.1:2335

后端会自动提供前端静态文件和 SPA 路由支持。
