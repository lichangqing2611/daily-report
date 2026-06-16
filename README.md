# AI 科技日报

每日自动抓取 RSS 资讯源，通过 DeepSeek V4 Pro 进行智能分类、摘要和去重，生成自包含的 HTML 日报。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 设置 API Key
export DEEPSEEK_API_KEY="your-key"

# 生成当日报告
python3 run.py

# 指定日期
python3 run.py --date 2026-06-15

# 仅抓取，不调用 LLM
python3 run.py --fetch-only
```

## 配置

编辑 `config.yaml` 可调整 RSS 源、LLM 参数、输出目录等。配置文件支持 `${ENV_VAR}` 环境变量插值。

## 项目结构

```
├── run.py              # 入口
├── config.yaml         # 配置文件
├── src/
│   ├── sources/        # RSS 插件（自动注册）
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

通过自建 RSS 聚合服务 `http://rss.charleslee.cn/feeds/all.atom` 获取资讯。
