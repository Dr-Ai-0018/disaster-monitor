# US Workflow Server

新一代工作流后台，与 `us-public-server` 并列存在。

目标：

- 复用旧项目的 `.env` / `config.json` / `database/disaster.db` / `storage`
- 将旧项目视为遗留数据与逻辑参考
- 由新项目接管“池子视图、人工审核、推理/摘要重置、日报候选”等工作流能力
- 支持让旧项目进入“只读遗留模式”，避免双服务同时消费任务

