# AI 科技日报

每日自动抓取科技资讯（雷峰网、半导体行业观察、量子位、火山引擎），结合 GitHub Trending 和 BAAI 热门论文，经由 DeepSeek V4 Pro 智能分类、摘要和去重，生成自包含的 HTML 日报。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 在 .env 中设置 API Key
echo 'DEEPSEEK_API_KEY="your-key"' > .env

# 生成当日报告（仅新增文章）
python3 run.py

# 指定日期
python3 run.py --date 2026-06-15

# 处理当天所有文章（跳过去重）
python3 run.py --date 2026-06-15 --all

# 仅抓取，不调用 LLM
python3 run.py --fetch-only

# 验证配置和来源
python3 run.py --dry-run
```

## 命令行参数

| 参数 | 说明 |
|------|------|
| `--date YYYY-MM-DD` | 指定报告日期，默认今天 |
| `--all` | 处理所有文章，跳过缓存去重 |
| `--fetch-only` | 仅抓取并缓存，不调用 LLM |
| `--dry-run` | 验证配置和来源可用性，不产生输出 |
| `--config custom.yaml` | 使用自定义配置文件 |

## 配置

编辑 `config.yaml` 可调整信息源、LLM 参数、输出目录等。配置文件支持 `${ENV_VAR}` 环境变量插值。API Key 通过 `.env` 文件或环境变量设置。

### 信息源配置

```yaml
sources:
  GitHubTrending:
    enabled: true
  BAAIHub:
    enabled: true
    max_papers: 30
  LeiphoneSource:
    enabled: true
    max_articles: 15
  SemiInsightsSource:
    enabled: true
    max_articles: 15
  QbitaiSource:
    enabled: true
    max_articles: 15
  VolcengineSource:
    enabled: true
    max_articles: 10
  RSSFeed:
    enabled: false   # 保留备用，默认关闭
```

### `source_urls` 配置

```yaml
source_urls:
  GitHub Trending: "https://github.com/trending"
  BAAI Hub: "https://hub.baai.ac.cn/papers?model=hotness&time=week"
  雷峰网: "https://www.leiphone.com/"
  半导体行业观察: "http://www.semi-insights.com/"
  量子位: "https://www.qbitai.com/"
  火山引擎: "https://developer.volcengine.com/articles/"
```

未配置 URL 的信息源将以纯文本显示。

## 报告页面

生成的 HTML 报告包含三个标签页：

- **科技新闻**：LLM 分类整理的新闻文章，包含今日头条和按类别分组展示
- **GitHub Trending**：独立展示 GitHub 当日热门项目，按当日新增 Star 数降序排列。每项显示项目名（链接至 GitHub）、编程语言、总 Star 数、每日新增 Star 数、Fork 数（同行展示），下方为 LLM 生成的中文介绍
- **热门论文**：BAAI Hub 热度周榜 Top 30 论文。每篇论文显示排名徽章、英文原标题及超链接、中文翻译标题、完整中文摘要

## 信息源

| 信息源 | 来源 | 技术路线 |
|--------|------|----------|
| GitHub Trending | https://github.com/trending | BeautifulSoup 网页抓取 |
| BAAI 热门论文 | https://hub.baai.ac.cn/papers | Playwright 滚动加载（30 篇） |
| 雷峰网 | https://www.leiphone.com/ | BeautifulSoup 网页抓取 |
| 半导体行业观察 | http://www.semi-insights.com/ | BeautifulSoup 网页抓取 |
| 量子位 | https://www.qbitai.com/ | BeautifulSoup 网页抓取 |
| 火山引擎 | https://developer.volcengine.com/articles/ | JSON API 直连 |
| RSS 聚合 | http://rss.charleslee.cn/feeds/all.atom | 保留备用，默认关闭 |

## 项目结构

```
├── run.py              # 入口
├── config.yaml         # 配置文件
├── src/
│   ├── sources/        # 信息源插件（自动注册）
│   │   ├── base.py             # SourcePlugin 基类
│   │   ├── github_trending.py  # GitHub Trending
│   │   ├── baai_hub.py         # BAAI 热门论文
│   │   ├── leiphone.py         # 雷峰网
│   │   ├── semi_insights.py    # 半导体行业观察
│   │   ├── qbitai.py           # 量子位
│   │   ├── volcengine.py       # 火山引擎
│   │   └── rss_feed.py         # RSS（备用）
│   ├── processor.py    # DeepSeek 批量分类/摘要
│   ├── renderer.py     # Jinja2 → HTML
│   ├── cache.py        # SQLite 去重
│   ├── config.py       # 配置解析
│   ├── fetcher.py      # 并发抓取调度
│   └── models.py       # 数据模型
├── templates/          # Jinja2 模板
├── output/             # 生成的报告
└── cache/              # 去重数据库
```
