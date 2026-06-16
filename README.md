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
