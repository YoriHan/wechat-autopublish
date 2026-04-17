# wechat-autopublish

每天自动抓取海外 AI/科技文章，用 Claude 翻译成中文，推送到微信公众号草稿箱，一键发布。

## 工作流

```
每天 8:00 CST
    ↓
抓取 RSS + 网页（OpenAI、DeepMind、Anthropic、Simon Willison 等）
    ↓
评分选出当日最佳文章（新鲜度 + 来源权威性 + 关键词相关度）
    ↓
Claude Sonnet 翻译为公众号风格中文
    ↓
自动生成封面图（Gemini Imagen / DALL-E，可选）
    ↓
提交到微信公众号草稿箱
    ↓
Bark / PushPlus 推送手机通知
    ↓
用户在公众号后台一键发布
```

用户只需两个动作：收到通知 → 公众号后台发布。

## 功能

- **多来源聚合**：OpenAI、Google DeepMind、Anthropic、Simon Willison、The Batch、Hacker News 等
- **智能评分**：新鲜度（48h 内满分）× 来源权重 × 关键词相关度，< 30 分自动跳过
- **去重**：SQLite 记录已发布 URL，不重复推送
- **Claude 翻译**：保留英文技术术语，适配公众号阅读风格，带编者按
- **封面图生成**：调用 Gemini Imagen 或 DALL-E 生成主题封面，失败时静默跳过
- **两种排版**：内置 inline-CSS 模式，或集成 [md2wechat](https://github.com/doocs/md) 获得更精美样式
- **通知**：优先 Bark（iOS），备选 PushPlus（微信）
- **调度**：macOS launchd（本地）或 GitHub Actions（云端）

## 快速开始

### 1. 环境准备

```bash
git clone https://github.com/your-username/wechat-autopublish
cd wechat-autopublish
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`：

```env
ANTHROPIC_API_KEY=sk-ant-...          # 必须
WECHAT_APP_ID=wx...                   # 必须，公众号后台 → 开发 → 基本配置
WECHAT_APP_SECRET=...                 # 必须
WECHAT_COVER_MEDIA_ID=...             # 可选，预上传封面图的 media_id（备用）
BARK_KEY=...                          # 推荐，Bark iOS app 的设备 key
PUSHPLUS_TOKEN=...                    # 备选，pushplus.plus 的 token
GEMINI_API_KEY=...                    # 可选，用于 AI 封面图生成
OPENAI_API_KEY=...                    # 可选，Gemini 失败时备用
USE_MD2WECHAT=false                   # true = 使用 md2wechat 排版（需本地安装）
WECHAT_THEME=autumn-warm              # md2wechat 主题名
```

**获取 WeChat 凭据：** 登录 [mp.weixin.qq.com](https://mp.weixin.qq.com) → 设置与开发 → 基本配置

### 3. 测试运行

```bash
# dry run：不调用微信 API，不发通知
DRY_RUN=1 python pipeline.py

# 完整运行
python pipeline.py
```

### 4. 配置定时任务

**macOS launchd（推荐）：**

```bash
cat > ~/Library/LaunchAgents/com.wechat.autopublish.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.wechat.autopublish</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/YOUR_USERNAME/wechat-autopublish/.venv/bin/python3</string>
        <string>/Users/YOUR_USERNAME/wechat-autopublish/pipeline.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>8</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>WorkingDirectory</key>
    <string>/Users/YOUR_USERNAME/wechat-autopublish</string>
    <key>StandardOutPath</key>
    <string>/Users/YOUR_USERNAME/wechat-autopublish/pipeline.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/YOUR_USERNAME/wechat-autopublish/pipeline.err</string>
</dict>
</plist>
EOF

launchctl load ~/Library/LaunchAgents/com.wechat.autopublish.plist
```

**GitHub Actions（云端，无需开机）：** 参见 [`.github/workflows/`](.github/workflows/)，在仓库 Settings → Secrets 中配置环境变量即可。

## 文件结构

```
wechat-autopublish/
├── pipeline.py        # 主入口，串联所有模块
├── config.py          # 配置加载 + 信源列表
├── fetcher.py         # RSS 抓取 + 网页全文提取
├── scorer.py          # 文章评分与选优
├── translator.py      # Claude 翻译
├── formatter.py       # Markdown → WeChat HTML（inline CSS）
├── wechat.py          # 微信 Draft API 封装
├── notifier.py        # Bark / PushPlus 通知
├── image_gen.py       # AI 封面图生成（可选）
├── db.py              # SQLite 去重记录
├── requirements.txt
└── .env.example
```

## 评分规则

| 维度 | 权重 | 说明 |
|------|------|------|
| 新鲜度 | 40 分 | 48h 内满分，7 天线性衰减至 0 |
| 来源权重 | 35 分 | Tier 1（OpenAI、Anthropic 等）35 分，Tier 2 20 分 |
| 关键词相关度 | 25 分 | 命中 claude、llm、agent 等关键词，每个 +5 分 |

总分 < 30 时不发布，推送"今日无优质内容"通知。

## 注意事项

- 微信公众号 Access Token 有效期 2 小时，程序自动刷新并缓存到 `wechat_token.db`
- `published.db` 记录已发布文章，防止重复发布，**不要删除**
- 封面图生成为可选功能，不配置 API Key 时直接跳过，使用 `WECHAT_COVER_MEDIA_ID` 静态封面
- macOS 用户建议开启"网络访问时唤醒"（系统设置 → 节能），避免 8 点时 Mac 休眠

## License

MIT
