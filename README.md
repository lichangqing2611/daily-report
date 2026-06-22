# AI 科技日报

每日自动抓取微信公众号资讯（通过 wewe-rss）和 GitHub Trending，经由 DeepSeek V4 Pro 智能分类、摘要和去重，生成自包含的 HTML 日报。

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

编辑 `config.yaml` 可调整 RSS 源、LLM 参数、输出目录等。配置文件支持 `${ENV_VAR}` 环境变量插值。API Key 通过 `.env` 文件或环境变量设置。

### `source_urls` 配置

在 `config.yaml` 的 `source_urls` 段可配置信息源名称到官网 URL 的映射，用于报告底部信息源超链接：

```yaml
source_urls:
  GitHub Trending: "https://github.com/trending"
  雷峰网: "https://www.leiphone.com/"
  量子位: "https://www.qbitai.com/"
```

未配置 URL 的信息源将以纯文本显示。

## 报告页面

生成的 HTML 报告包含两个标签页：

- **科技新闻**：LLM 分类整理的新闻文章，包含今日头条和按类别分组展示
- **GitHub Trending**：独立展示 GitHub 当日热门项目，按当日新增 Star 数降序排列。每项显示项目名（链接至 GitHub）、编程语言、总 Star 数、每日新增 Star 数、Fork 数（同行展示），下方为 LLM 生成的中文介绍

## 项目结构

```
├── run.py              # 入口
├── config.yaml         # 配置文件
├── src/
│   ├── sources/        # 新闻源插件（自动注册）
│   ├── processor.py    # DeepSeek 批量分类/摘要
│   ├── renderer.py     # Jinja2 → HTML
│   ├── cache.py        # SQLite 去重
│   ├── config.py       # 配置解析
│   └── models.py       # 数据模型
├── templates/          # Jinja2 模板
├── output/             # 生成的报告
└── cache/              # 去重数据库
```

## 信息源

- 微信公众号聚合：`http://rss.charleslee.cn/feeds/all.atom`（基于 wewe-rss）
- GitHub Trending
