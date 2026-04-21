# wechat-autopublish

每天自动从 53 个 AI/技术信息源抓取优质文章，用 DeepSeek 翻译成中文，写入 Notion 供人工选稿，最终发布到微信公众号草稿箱。

---

## 功能概览

| 功能 | 说明 |
|------|------|
| 🔍 多源抓取 | 53 个 Twitter/X 账号 + 16 个 RSS 源，每天自动采集 |
| 🤖 AI 翻译 | DeepSeek API，保留原文结构，自动生成中文标题 |
| 📋 人工选稿 | 每天 8am 推送 Top 5 候选，在 Notion 里选一篇，12pm 自动发布 |
| 📖 Notion 存档 | 全文写入 Notion，图片直接上传至 Notion 文件存储 |
| 🎨 4 套微信排版 | 绿/蓝/极简/紫，inline CSS，直接复制到公众号编辑器 |
| 💬 养虾社 CTA | 每篇文章开头结尾自动插入品牌 CTA（橙色 `#FF6600` 加粗） |
| 📱 消息推送 | Bark（iOS）/ PushPlus 推送选稿通知和发布结果 |
| 🔗 手动触发 | 把推特链接或文章 URL 丢给 AI，秒级触发完整流水线 |

---

## 两段式每日流水线

```
08:00 CST — Stage 1: 抓取 & 选稿
  ├─ 抓取所有 RSS + Twitter 信息源
  ├─ 打分排序，取 Top 5 候选
  ├─ 存入 Notion 候选库（字段自动初始化）
  └─ Bark/PushPlus 推送候选列表 + Notion 链接

        ↕  你在 Notion 候选库把想发的那篇 Status 改为「选中」
           （不操作则 12pm 自动发 Top 1）

12:00 CST — Stage 2: 翻译 & 发布
  ├─ 读取「选中」候选（或自动取 Top 1）
  ├─ 抓取文章全文 + 封面图
  ├─ DeepSeek 翻译成中文，提取中文标题
  ├─ 写入 Notion 存档库（含图片上传）
  ├─ 生成 4 套微信 HTML → 存入 Notion code block 供复制
  ├─ 推送至微信公众号草稿箱（如已配置）
  └─ 推送发布完成通知
```

> **手动单次触发**：把链接发给 Daruma（团队 AI），或在 GitHub Actions 页面
> 点 "Run workflow" 填入链接，自动跑完 fetch → translate → publish 全流程。

---

## 信息源

### RSS 源（16 个）

| 来源 | Tier |
|------|------|
| OpenAI Blog | 1 |
| Google DeepMind Blog | 1 |
| Anthropic News | 1 |
| Anthropic Research | 1 |
| Claude Blog | 1 |
| HuggingFace Blog | 1 |
| Simon Willison's Blog | 1 |
| TechCrunch AI | 1 |
| VentureBeat AI | 1 |
| Papers With Code | 2 |
| The Batch (DeepLearning.AI) | 2 |
| MIT Technology Review | 2 |
| The Verge AI | 2 |
| Hacker News AI（50+ 分） | 2 |
| Bloomberg Tech | 2 |
| WSJ Tech | 2 |

### Twitter/X 账号（53 个，via RSSHub）

fetcher 从推文正文中提取**外链文章 URL**，不直接发推文内容。

**AI 实验室 & 创始人**
`sama` · `karpathy` · `ylecun` · `demishassabis` · `AnthropicAI` · `OpenAI` · `GoogleAI` · `MetaAI` · `MistralAI` · `xai`

**研究员 & 实践者**
`emollick` · `DrJimFan` · `gdb` · `fchollet` · `JeffDean` · `ilyasut` · `npew` · `hardmaru`

**A 类：每天发论文/文章（高频必追）**
`_akhaliq` · `omarsar0` · `chiphuyen` · `rasbt` · `svpino` · `reach_vb` · `arankomatsuzaki` · `cwolferesearch`

**B 类：研究员 & 从业者**
`jeremyphoward` · `goodside` · `ClementDelangue` · `jackclarkSF` · `eugeneyan` · `srush_nlp` · `HamelHusain` · `AravSrinivas` · `GaryMarcus`

**B 类：AI 平台 & 组织**
`huggingface` · `LangChainAI` · `weights_biases` · `ReplicateHQ` · `Scale_AI` · `Gradio` · `llama_index` · `MSFTResearch`

**Tech 分析 & VC**
`paulg` · `pmarca` · `benedictevans` · `netflixtech`

**C 类：工程 & 开发者教育**
`GergelyOrosz` · `addyosmani` · `swyx` · `b0rk` · `danluu` · `copyconstruct`

---

## 微信排版

每篇文章自动生成 4 套主题 HTML，存入 Notion code block，粘贴进微信公众号编辑器直接使用。

| 主题 | 主色 | 适合 |
|------|------|------|
| 🟢 绿色清新 | `#07C160` | 日常推文 |
| 🔵 蓝色商务 | `#1677FF` | 技术深度文 |
| ⚫ 极简黑白 | `#222222` | 长文阅读 |
| 🟣 紫色优雅 | `#7C3AED` | 精选内容 |

所有主题共同特性：
- 全部 inline CSS，兼容微信公众号编辑器
- 开头和结尾自动插入养虾社 CTA：
  > 关注**养虾社**，一个专注于AI优质内容分享的中文社区。

  （12px 加粗，"养虾社"三字橙色 `#FF6600`）

---

## 文章评分规则

| 维度 | 说明 |
|------|------|
| 新鲜度 | 48h 内满分，7 天线性衰减 |
| 来源权重 | Tier 1（OpenAI、Anthropic 等）> Tier 2 |
| 关键词相关度 | 命中 claude、llm、agent、reasoning 等 AI 关键词加分 |

总分 < 30 时跳过，推送"今日无优质内容"通知。

---

## 快速部署

### 1. Fork & Clone

```bash
git clone https://github.com/YoriHan/wechat-autopublish.git
cd wechat-autopublish
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

| 变量 | 必填 | 说明 |
|------|------|------|
| `DEEPSEEK_API_KEY` | ✅ | [DeepSeek 控制台](https://platform.deepseek.com) 获取 |
| `NOTION_TOKEN` | ✅ | Notion Integration token |
| `NOTION_DATABASE_ID` | ✅ | 文章存档数据库 ID |
| `NOTION_CANDIDATES_DATABASE_ID` | 推荐 | 每日候选数据库 ID（不填则跳过人工选稿，直接发 Top 1） |
| `WECHAT_APP_ID` | 可选 | 微信公众号 AppID |
| `WECHAT_APP_SECRET` | 可选 | 微信公众号 AppSecret |
| `WECHAT_COVER_MEDIA_ID` | 可选 | 默认封面图 media_id |
| `BARK_KEY` | 可选 | iOS Bark 推送 key |
| `PUSHPLUS_TOKEN` | 可选 | PushPlus 推送 token |
| `RSSHUB_BASE_URL` | 可选 | 自托管 RSSHub 地址（不填用公共实例） |

### 3. 创建 Notion 数据库

**文章存档库**（`NOTION_DATABASE_ID`）
- 在 Notion 新建全页数据库
- 将 Integration 加入该数据库
- 从 URL 复制 32 位数据库 ID 填入环境变量

**每日候选库**（`NOTION_CANDIDATES_DATABASE_ID`）
- 新建另一个空的全页数据库（字段由 pipeline 自动创建）
- 每天 8am 自动写入 Top 5，把想发的那篇 `Status` 改为「选中」即可

### 4. 配置 GitHub Secrets

仓库 Settings → Secrets and variables → Actions，添加所有环境变量（与 `.env` 同名）。

### 5. 本地验证

```bash
# 干跑，不写 Notion 不发微信
DRY_RUN=true python pipeline.py

# 只跑 Stage 1（抓取 + 选稿推送）
python pipeline.py --stage fetch

# 指定文章 URL 直接发布
MANUAL_URL=https://example.com/article python pipeline.py
```

---

## GitHub Actions 调度

```
00:00 UTC (08:00 CST)  →  python pipeline.py --stage fetch
04:00 UTC (12:00 CST)  →  python pipeline.py --stage publish
```

手动触发选项（Actions 页面 → Run workflow）：
- **留空**：完整单次流程（fetch → publish）
- **填入 URL**：对指定链接跑全流程
- **填入 stage**：单独跑 `fetch` 或 `publish`

---

## 手动触发（日常使用）

在推特上发现好文章 → 直接把链接发给 **Daruma**（团队 AI） → 她自动调 GitHub Actions API 触发完整流水线 → 结果写入 Notion + 推送通知。

支持：
- Twitter/X 推文链接（自动提取推文中的外链文章）
- 文章直链
- 任意网页 URL

---

## 自托管 RSSHub（提高 Twitter 稳定性）

公共 rsshub.app 对 Twitter 可能不稳定。有服务器时建议自托管：

```bash
docker run -d -p 1200:1200 diygod/rsshub
```

设置环境变量：
```
RSSHUB_BASE_URL=http://your-server:1200
```

---

## 文件结构

```
wechat-autopublish/
├── pipeline.py          # 主入口：两段式 + 单次 + 手动触发
├── config.py            # 环境变量 + 53 个 Twitter 账号 + 信息源列表
├── fetcher.py           # RSS 抓取 + 推文文章链接提取 + 全文爬取
├── scorer.py            # 文章打分（相关性 + 来源权重 + 新鲜度）
├── translator.py        # DeepSeek 翻译 + 中文标题提取
├── formatter.py         # 4 套微信 HTML 主题 + 养虾社 CTA
├── notion_writer.py     # Notion 写入（含图片直传）
├── candidate_store.py   # 候选库读写（自动建列）
├── screenshot.py        # Playwright 截图 + 上传 GitHub
├── notifier.py          # Bark / PushPlus 推送
├── wechat.py            # 微信公众号草稿箱 API
├── db.py                # SQLite 已发布 URL 去重
├── image_gen.py         # 封面图生成（可选）
├── requirements.txt
├── .env.example
└── .github/
    └── workflows/
        └── daily-publish.yml   # 两段 cron + 手动触发 + stage 参数
```

---

## 注意事项

- 微信公众号 Access Token 有效期 2 小时，程序自动刷新并缓存到 `wechat_token.db`
- `published.db` 记录已发布 URL 防重复，**不要删除**
- `mistune` 版本固定在 `2.0.5`，**不要升级到 3.x**（API 不兼容）
- Twitter 抓取依赖 RSSHub；公共实例不稳定时建议自托管

---

## License

MIT
