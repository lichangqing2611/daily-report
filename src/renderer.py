from pathlib import Path
from datetime import date

from jinja2 import Environment, FileSystemLoader

from src.models import Report


class Renderer:
    def __init__(self, template_dir: str = "./templates", output_dir: str = "./output"):
        self.template_dir = Path(template_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, report: Report) -> Path:
        template = self.env.get_template("report.html")
        html = template.render(report=report)

        filename = f"report-{report.report_date.isoformat()}.html"
        output_path = self.output_dir / filename
        output_path.write_text(html, encoding="utf-8")

        return output_path

    def render_index(self, reports: list[dict]) -> Path:
        """Render an index page listing recent reports."""
        index_html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI 科技日报 - 历史报告</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif; max-width: 600px; margin: 40px auto; padding: 0 20px; }
    h1 { font-size: 24px; margin-bottom: 24px; }
    .report-item { display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid #eee; }
    .report-item a { color: #2563eb; text-decoration: none; font-weight: 500; }
    .report-item a:hover { text-decoration: underline; }
    .report-date { color: #6b7280; font-size: 14px; }
    .report-count { color: #9ca3af; font-size: 13px; }
  </style>
</head>
<body>
  <h1>AI 科技日报 - 历史报告</h1>
"""
        for r in reports:
            filename = Path(r["file_path"]).name
            index_html += f"""  <div class="report-item">
    <div>
      <a href="{filename}">{r["report_date"]}</a>
      <span class="report-count">({r["article_count"]} 篇)</span>
    </div>
    <span class="report-date">{r.get("generated_at", "")}</span>
  </div>
"""

        index_html += """</body></html>"""

        index_path = self.output_dir / "index.html"
        index_path.write_text(index_html, encoding="utf-8")
        return index_path
