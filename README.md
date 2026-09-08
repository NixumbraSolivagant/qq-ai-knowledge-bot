# QQ AI Knowledge Bot

一个基于现成工具的 QQ 群 AI 学习助手：定时分享 AI 知识，支持群内问答、追问和进阶测验。



## 功能

- 每天在 08:00–18:00 随机推送一条 AI 短知识
- `今日知识`：生成适合群聊阅读的短内容
- `深度知识`：生成较完整的长内容
- `问 什么是推测解码？`：AI 技术问答
- `详问 RAG 如何评估？`：详细回答
- `追问 它的主要瓶颈是什么？`：结合最近对话追问
- `@机器人 问题`：直接对话
- `出题`、`答 A`、`解析`：进阶单选题互动
- 并发读取国内外专业来源：OpenAI、Google AI、Microsoft Research、NVIDIA、arXiv，以及 Qwen、PaddlePaddle、GLM、MiniCPM、InternLM、ModelScope、RAGFlow 等官方项目 Release
- QQ 不支持的 LaTeX 会自动转换成纯文本
- API 失败时使用本地高阶备用内容
- 敏感内容、隐私窃取和危险操作请求会被拦截

## 架构

```text
QQ / 群成员
    │
    ▼
NapCat（外部 QQ 接入端）
    │ OneBot V11 reverse WebSocket
    ▼
NoneBot 2（本项目，默认 127.0.0.1:3001）
    │ HTTPS
    ▼
火山方舟 Responses API
```

NapCat 是外部依赖，请从其官方项目获取并自行安装。本仓库不重新分发 NapCat 或 QQ 文件。

## 环境要求

- Linux/macOS/Windows 均可运行 NoneBot；本文以 Ubuntu 22.04+ 为例
- Python 3.10+
- 一个已经安装并登录的 OneBot V11 接入端，例如 NapCat
- 火山方舟 API Key
- 目标 QQ 群中允许机器人账号发言

## 从零安装

### 1. 获取项目

```bash
git clone https://github.com/NixumbraSolivagant/qq-ai-knowledge-bot.git
cd qq-ai-knowledge-bot
```

### 2. 创建 Python 环境

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

### 3. 创建本地配置

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

至少填写：

```env
KNOWLEDGE_GROUP_IDS=你的群号
ARK_API_KEY=你的火山方舟Key
```

不要把真实 `.env` 提交到 Git。API Key 如果曾经发到聊天、截图或公开仓库，应立即撤销并重新生成。

### 4. 配置 NapCat / OneBot

在 NapCat 的网络配置中创建 **WebSocket 客户端**，不要创建 WebSocket 服务器：

```text
URL: ws://127.0.0.1:3001/onebot/v11/ws
消息格式: Array
启用: 是
```

如果设置了 OneBot Token，NapCat 和 `.env` 的 `ONEBOT_ACCESS_TOKEN` 必须完全一致；不使用 Token 时两边都留空。

QQ 登录和扫码必须由账号本人完成。请使用专用 QQ 账号，并遵守 QQ、NapCat 和相关服务的使用规则。

### 5. 启动

终端一启动机器人：

```bash
source .venv/bin/activate
python bot.py
```

看到以下日志说明 NoneBot 已启动：

```text
Uvicorn running on http://127.0.0.1:3001
```

NapCat 连接后应看到：

```text
Bot <your_bot_id> connected
```

### 6. 测试

在目标群发送：

```text
功能
今日知识
问 Transformer 的 KV Cache 为什么会占显存？
出题
```

## 开机启动（Linux systemd）

项目提供了 NoneBot 的 systemd 模板。假设项目放在 `~/qq-ai-knowledge-bot`：

```bash
mkdir -p ~/.config/systemd/user
sed "s/%i/$USER/g" deploy/systemd/qq-knowledge-bot.service \
  > ~/.config/systemd/user/qq-knowledge-bot.service
systemctl --user daemon-reload
systemctl --user enable --now qq-knowledge-bot.service
loginctl enable-linger "$USER"
```

查看日志：

```bash
journalctl --user -u qq-knowledge-bot -f
```

NapCat 应按其官方文档单独配置为开机启动。不要把 NapCat 的安装包、运行目录或登录数据复制进本仓库。

## 配置说明

- `KNOWLEDGE_GROUP_IDS`：目标群号，多个群用英文逗号分隔
- `KNOWLEDGE_TOPICS`：每日知识方向
- `ARK_API_KEY`：火山方舟 API Key，仅放在本地 `.env`
- `ARK_MODEL`：方舟模型名称
- `CHAT_COOLDOWN_SECONDS`：每位用户问答冷却时间
- `SOURCE_CACHE_SECONDS`：近期资料缓存时间，默认 6 小时
- `SOURCE_TIMEOUT_SECONDS`：单轮资料抓取的超时上限，默认 6 秒
- `SOURCE_ITEMS_PER_REQUEST`：每次交给模型凝练的文章数量，默认 1 篇，避免混合多篇文章

资料抓取是软依赖：某个网站不可访问时会自动跳过，所有来源都不可用时仍会使用本地专题知识，不会让机器人崩溃。

`今日知识` 会选择一篇正文足够完整的专业文章，先生成凝练稿，再进行一次逐句原文对照审校。程序还会校验数字、证据编号和来源网址，并自动附上两条原文摘录；未通过校验时不会发送未经证实的摘要。

普通内容是短版；想看长内容可以使用 `深度知识`、`详问`、`详细展开` 等表达。

## 开发检查

```bash
python -m compileall -q bot.py plugins
```

## 安全与隐私

- 不要提交 `.env`、API Key、OneBot Token、WebUI Token、二维码、QQ 配置、聊天记录或个人信息。
- 本项目默认只访问白名单 AI 资料域名。
- 模型输出会经过敏感内容和链接校验，但 AI 输出仍应人工复核。
- 不要使用机器人提供的内容替代医疗、法律或金融专业意见。

## License

MIT，见 `LICENSE`。
