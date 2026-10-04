# ClipVault 公开发行仓库配置与运维手册

本手册记录公开仓库 `SimileciWH/clipvault-releases` 的安全配置与日常发版操作标准，由仓库管理员执行。

---

## 1. 架构与安全防护准则

本方案利用 GitHub 公开仓库的标准 Hosted Runner（macOS-15 与 Windows-2025）完全免费构建二进制安装包，通过只读 Deploy Key 检出私有源码仓库 `SimileciWH/clipvault`。

**核心安全防线：**
1. **只读凭据隔离**：Deploy Key 严格为只读权限，绝无私有仓库写权限；构建产物仅上传打包编译后的二进制 zip 与签名，私有源码绝不上传。
2. **环境门禁隔离**：敏感机密（`RELEASE_SIGN_PRIVATE_KEY`、`ADMIN_TOKEN`）仅分配在 `release` Environment 中，仅在人工审批的发布阶段注入，构建/冒烟阶段环境完全无凭据。
3. **多重泄漏扫描**：每个 Job 退出前通过 `leak_scan.py` 严格校验哈希指纹，命中任何私有注释或代码段立即熔断退出。

---

## 2. 初始安全配置（仓库管理员执行）

### 步骤 1：生成并配置只读 Deploy Key
在管理员本地终端执行：
```bash
# 生成专用 Ed25519 密钥对（不要设置密码）
ssh-keygen -t ed25519 -C "clipvault-release-builder" -f ~/.ssh/clipvault_deploy_key

# 1. 将公钥添加至私有仓库 (SimileciWH/clipvault)
# 浏览器访问: https://github.com/SimileciWH/clipvault/settings/keys
# 点击 "Add deploy key":
# Title: clipvault-releases-builder-ro
# Key: 粘贴 ~/.ssh/clipvault_deploy_key.pub 内容
# ⚠️ 确保 "Allow write access" 保持未勾选（只读）！

# 2. 将私钥写入公开仓库的 Environment Secret 或 Repo Secret
gh secret set CLIPVAULT_DEPLOY_KEY --repo SimileciWH/clipvault-releases < ~/.ssh/clipvault_deploy_key
```

### 步骤 2：创建 `release` 环境与审批人
1. 访问公开仓库设置：`https://github.com/SimileciWH/clipvault-releases/settings/environments`
2. 点击 **New environment**，名称输入：`release`
3. 配置环境规则：
   - 勾选 **Required reviewers**，添加仓库管理员账号（每次发版签名发布需手动点击批准）。
   - 勾选 **Deployment branches**，选择 **Selected branches**，添加规则仅允许 `main`。
4. 在该环境下的 **Environment secrets** 录入敏感密钥：
   ```bash
   # 录入签名私钥（十六进制，从安全脱机介质读入）
   gh secret set RELEASE_SIGN_PRIVATE_KEY --env release --repo SimileciWH/clipvault-releases

   # 录入服务器管理员令牌
   gh secret set ADMIN_TOKEN --env release --repo SimileciWH/clipvault-releases
   ```

### 步骤 3：仓库通用安全设置
进入 `https://github.com/SimileciWH/clipvault-releases/settings`：
1. **Actions 权限**（Settings → Actions → General）：
   - Actions permissions: 选中 **Allow all actions and reusable workflows**（或限 actions/*）。
   - Artifact and log retention: 设置为 **1 day**（防止构建留存过期文件）。
   - Fork pull request workflows: 勾选 **Require approval for all outside collaborators**。
   - Workflow permissions: 选择 **Read repository contents and packages permissions**（默认只读）。
2. **分支保护规则**（Settings → Branches）：
   - 为 `main` 分支添加 Ruleset 或 Branch protection：
     - Require a pull request before merging.
     - Require status checks to pass before merging.
     - Do not allow bypassing the above settings.

---

## 3. 标准发版流程（日常运维）

每次发版严格遵循三阶段：**Dry Run 校验 → 预发布复核 → 正式生产发布**。

### 阶段一：Dry Run（验证构建与安全扫描）
在私有仓库 `SimileciWH/clipvault` 确定待发布的 commit SHA（例如 `abcdef0123...`，必须已合并至 `main`）：
1. 访问公开仓库 Actions 页面：`https://github.com/SimileciWH/clipvault-releases/actions/workflows/release.yml`
2. 点击 **Run workflow**：
   - `SimileciWH/clipvault commit SHA`: 输入完整 40 位 hex SHA。
   - `Release channel`: 选择 `both`（同时构建源码与双平台二进制）。
   - `Dry run`: 勾选 `true`。
3. 观察构建矩阵 `macos-15` 与 `windows-2025` 完成，核查：
   - Smoke 测试通过。
   - Gate 门禁校验通过。
   - Leak scan 提示 `hits=0`，未发现私有代码泄漏。
   - Publish Job 自动跳过，无凭据泄露风险。

### 阶段二：生产发布（Sign, Publish & Register）
确认 Dry Run 100% 绿灯后：
1. 再次点击 **Run workflow**：
   - 输入相同的 commit SHA。
   - `Dry run`: 取消勾选（设为 `false`）。
2. 当流水线流转到 `publish` 阶段时，GitHub 将弹出 **Deployment review** 请求：
   - 检查提交的 commit SHA 与目标版本号是否一致。
   - 点击 **Approve and deploy**。
3. 流水线自动完成：
   - Ed25519 签名生成。
   - GitHub Releases 资产上传与 tag 发布。
   - 授权服务器元数据登记（`/api/admin/release`）。
   - `version.json` 合并与回写。

---

## 4. 匿名访问者核查规程（发版后验证）

发布完成后，以**未登录的无痕浏览器窗口（匿名身份）**验证公开透明度：
1. **下载测试**：
   - 访问 `https://github.com/SimileciWH/clipvault-releases/releases/latest`。
   - 下载 `clipvault-client-macos-arm64.zip` 与 `clipvault-client-windows-x64.zip`。
   - 解压检查：仅包含打包后的编译产物，不包含 `server/`、`tests/`、`docs/`、`AGENTS.md` 等内部文件。
2. **日志审计**：
   - 访问刚才运行的 GitHub Actions 公开运行日志。
   - 确认日志中没有任何代码块明文、Token、密钥或私有仓库分支细节被输出。
3. **落地页指针检查**：
   - 访问 `https://clipvault-server.vercel.app/api/release-manifest`。
   - 验证 `version`、`binaries.macos.version`、`binaries.windows.version` 与下载文件名完全对齐。

---

## 5. 凭据定期轮换计划（每 90 天）

每 90 天建议轮换一次 Deploy Key 与签名私钥：
1. 重新生成并上传 Deploy Key，删除旧 Key。
2. 生成新签名密钥对 `release-YYYY-MM`，更新客户端公钥清单后，更新 Environment Secret `RELEASE_SIGN_PRIVATE_KEY`。
