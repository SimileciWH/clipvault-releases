# ClipVault 官方发行仓库

ClipVault 是一款面向内容创作者与跨国社媒运营团队的短视频采集、多语言本地化翻译与自动化分发工具。
本仓库为 ClipVault 的公开官方发布与二进制资产分发中心，提供跨平台桌面客户端的正式构建版本与签名凭证。
用户在此可获取经过 Ed25519 密码学签名保障的原生客户端安装包及版本校验文件。

---

## 客户端下载

请前往本仓库的 [Releases 页面](https://github.com/SimileciWH/clipvault-releases/releases) 获取最新稳定版本：

| 平台 / 架构 | 安装包文件名 | 说明 |
|---|---|---|
| **macOS (Apple Silicon)** | `clipvault-client-<版本>-macos-arm64.zip` | 适用于 Apple M 系列芯片（arm64 原生架构） |
| **Windows (x64)** | `clipvault-client-<版本>-windows-x64.zip` | 适用于 64 位 Windows 10 / 11 操作系统 |
| **源码通用包** | `clipvault-client-<版本>.zip` | 跨平台源码运行包（供开发者或 Linux 用户参考） |

每个发行包附带对应的 `.zip.sig` 签名文件，用于验证安装包的完整性与来源真实性。

---

## 安全与签名验证

所有官方发布的安装包均在隔离构建环境中编译，并使用 Ed25519 密钥对进行签名。

### 1. 签名公钥
官方当前使用的发布密钥（`release-2026-01`）公钥十六进制（HEX）如下：
```text
6fb90cf805f181f9351c48d1b0f22a5318787771ef5b93611732ec89a0d50f48
```
*(注：该公钥内嵌于客户端 `clipvault/updater.py` 中用于静默自检)*

### 2. 签名验证消息格式
签名载荷由 4 行 UTF-8 文本组成，每行末尾以换行符 `\n` 结尾：
```text
<文件名>\n<版本号>\n<文件字节大小>\n<SHA256哈希值>\n
```

### 3. 本地验证示例（Python 3.11+）
```python
import hashlib
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# 文件路径与参数
pkg = Path("clipvault-client-1.7.1-macos-arm64.zip")
sig_hex = Path("clipvault-client-1.7.1-macos-arm64.zip.sig").read_text().strip()
public_key_hex = "6fb90cf805f181f9351c48d1b0f22a5318787771ef5b93611732ec89a0d50f48"

# 构造验证消息
version = "1.7.1"
digest = hashlib.sha256(pkg.read_bytes()).hexdigest()
message = f"{pkg.name}\n{version}\n{pkg.stat().st_size}\n{digest}\n".encode("utf-8")

# 执行验签
pubkey = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
pubkey.verify(bytes.fromhex(sig_hex), message)
print("✅ 签名验证成功：该安装包为官方未篡改版本！")
```

---

## 快速安装与启动

1. **解压**：将下载的 `.zip` 压缩包解压至常用目录（如桌面或文档），该解压目录即为 ClipVault 的本地家目录。
2. **启动**：
   - **macOS**：双击 `start.command`（首次提示未识别开发者时，在访达中右键点击选择“打开”即可）。
   - **Windows**：右键点击 `start.ps1`，选择“使用 PowerShell 运行”。
3. **激活**：启动后系统将自动打开 `http://127.0.0.1:8000` 设置界面，输入授权许可证（License Key）完成绑定。

---

## 自动更新说明

ClipVault 客户端内置静默更新管理机制：
- 客户端在启动和后台心跳时自动检查远端最新版本。
- 检测到可用更新时，将在后台下载经 Ed25519 签名验证的新版本到独立的版本目录下，自动完成切换。
- 本地任务数据目录与配置文件位于家目录层级，跨版本持久共享，自动更新绝不会丢失本地历史数据。

---

## 问题反馈与支持

如在安装、启动或使用过程中遇到任何问题，欢迎通过本仓库的 [GitHub Issues](https://github.com/SimileciWH/clipvault-releases/issues) 提交反馈。
提交反馈时请附带本地日志摘要（位于解压目录下的 `data/logs/clipvault.log`），请注意在发布前抹除个人敏感隐私信息。
