import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


def prune_old_reports(output_dir: str, keep_days: int) -> list[str]:
    output_path = Path(output_dir)
    if not output_path.exists():
        return []

    cutoff = datetime.now() - timedelta(days=keep_days)
    deleted = []

    for html_file in output_path.glob("*.html"):
        try:
            mtime = datetime.fromtimestamp(html_file.stat().st_mtime)
            if mtime < cutoff:
                html_file.unlink()
                deleted.append(str(html_file))
                logger.info(f"Deleted old report: {html_file.name}")
        except OSError as e:
            logger.warning(f"Failed to delete {html_file.name}: {e}")

    return deleted
