# 贡献指南

感谢你对因子量化交易系统的关注！无论是报告 Bug、提出功能建议还是提交代码，都非常欢迎。

---

## 🚦 行为准则

- 保持友善和专业
- 尊重不同的观点和经验
- 建设性地提出批评
- 关注对社区最有利的事情

---

## 📋 如何贡献

### 报告 Bug

1. 在 Issues 中搜索是否已有相同问题
2. 使用清晰的标题描述问题
3. 提供以下信息：
   - 操作系统和版本
   - Python/Node.js 版本
   - 复现步骤
   - 预期行为 vs 实际行为
   - 相关日志或截图

### 提出功能建议

1. 在 Issues 中描述功能需求
2. 说明使用场景和期望效果
3. 如可能，描述实现思路

### 提交代码 (Pull Request)

1. **Fork 仓库** 并创建新分支
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **开发 & 测试**
   - 遵循项目现有的代码风格
   - 添加必要的注释
   - 确保代码可以正常运行

3. **提交变更**
   ```bash
   git commit -m "feat: 添加某某功能"
   ```
   提交信息格式: `<type>: <description>`
   - `feat`: 新功能
   - `fix`: Bug 修复
   - `docs`: 文档更新
   - `refactor`: 代码重构
   - `style`: 代码风格调整
   - `test`: 测试相关

4. **推送 & 创建 PR**
   ```bash
   git push origin feature/your-feature-name
   ```
   在 PR 描述中说明变更内容和原因。

---

## 🏗️ 开发环境设置

```bash
# 克隆仓库
git clone <your-fork-url>
cd factor-quantization-trader

# 后端
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 配置数据库和 Redis
python manage.py migrate

# 前端
cd frontend
npm install
npm run dev
```

---

## 📁 项目架构

详见 [AGENTS.md](./AGENTS.md)，包含完整的分层架构、数据流和设计决策说明。

---

## ✅ 代码审查清单

提交 PR 前请确认：

- [ ] 代码符合项目现有风格
- [ ] 新功能有适当的注释
- [ ] 不影响现有功能
- [ ] 数据库变更包含迁移文件
- [ ] API 变更同步更新了前端 API 层
- [ ] 相关文档已更新

---

## 📄 开源协议

本项目采用 MIT License。提交代码即表示你同意在该协议下发布你的贡献。
