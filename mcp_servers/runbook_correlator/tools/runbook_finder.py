"""Runbook finder tool - searches markdown runbook corpus."""

import logging
from pathlib import Path
from typing import Optional
import re

logger = logging.getLogger(__name__)


class RunbookFinder:
    """Find relevant runbooks from a markdown corpus.

    Runbooks are organized as markdown files with frontmatter metadata.
    The finder uses a combination of:
    1. Exact service/alert type matching via filename conventions
    2. Frontmatter metadata parsing (service, alert_types, severity)
    3. Content search for keywords

    Directory structure:
        runbooks/
        ├── payment-service/
        │   ├── pod-crash-loop.md
        │   ├── high-latency.md
        │   └── oom-errors.md
        ├── auth-service/
        │   └── ...
        └── general/
            ├── kubernetes-troubleshooting.md
            └── deployment-rollback.md
    """

    def __init__(self, runbooks_dir: Path):
        """Initialize runbook finder.

        Args:
            runbooks_dir: Directory containing runbook markdown files
        """
        self.runbooks_dir = Path(runbooks_dir)
        self.runbooks_cache = None
        logger.info(f"Initialized RunbookFinder (dir: {runbooks_dir})")

    def _load_runbooks(self) -> list[dict]:
        """Load and index all runbooks.

        Returns:
            List of runbook metadata dicts
        """
        if self.runbooks_cache is not None:
            return self.runbooks_cache

        runbooks = []

        if not self.runbooks_dir.exists():
            logger.warning(f"Runbooks directory does not exist: {self.runbooks_dir}")
            self.runbooks_cache = []
            return []

        # Find all markdown files
        for md_file in self.runbooks_dir.rglob("*.md"):
            try:
                metadata = self._parse_runbook(md_file)
                runbooks.append(metadata)
            except Exception as e:
                logger.error(f"Error parsing runbook {md_file}: {e}")

        logger.info(f"Loaded {len(runbooks)} runbooks")
        self.runbooks_cache = runbooks
        return runbooks

    def _parse_runbook(self, file_path: Path) -> dict:
        """Parse a runbook markdown file.

        Expected frontmatter format:
        ---
        service: payment-service
        alert_types:
          - pod_crash_loop
          - oom_killed
        severity: [high, critical]
        tags: [kubernetes, memory]
        ---

        Args:
            file_path: Path to markdown file

        Returns:
            Runbook metadata dict
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse frontmatter
        frontmatter = {}
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                import yaml
                try:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                except Exception as e:
                    logger.warning(f"Failed to parse frontmatter in {file_path}: {e}")

                # Rest of the content
                content = parts[2].strip()

        # Extract service from path or frontmatter
        service = frontmatter.get('service')
        if not service:
            # Try to infer from directory structure
            # e.g., runbooks/payment-service/... -> payment-service
            relative = file_path.relative_to(self.runbooks_dir)
            if len(relative.parts) > 1:
                service = relative.parts[0]

        # Extract alert types
        alert_types = frontmatter.get('alert_types', [])
        if isinstance(alert_types, str):
            alert_types = [alert_types]

        # Also try to infer from filename
        # e.g., pod-crash-loop.md -> pod_crash_loop
        filename_alert = file_path.stem.replace('-', '_')
        if filename_alert not in alert_types:
            alert_types.append(filename_alert)

        return {
            'path': str(file_path),
            'filename': file_path.name,
            'service': service,
            'alert_types': alert_types,
            'severity': frontmatter.get('severity', []),
            'tags': frontmatter.get('tags', []),
            'title': frontmatter.get('title', file_path.stem.replace('-', ' ').title()),
            'content': content,
            'frontmatter': frontmatter
        }

    def _match_score(
        self,
        runbook: dict,
        service: str,
        alert_type: str,
        severity: Optional[str]
    ) -> float:
        """Calculate match score for a runbook.

        Scoring:
        - Service exact match: +10
        - Alert type exact match: +10
        - Service partial match: +5
        - Alert type in list: +8
        - Severity match: +2
        - General runbook (no specific service): +1

        Args:
            runbook: Runbook metadata
            service: Target service name
            alert_type: Target alert type
            severity: Target severity (optional)

        Returns:
            Match score (higher is better)
        """
        score = 0.0

        # Service matching
        rb_service = runbook.get('service', '').lower()
        target_service = service.lower()

        if rb_service == target_service:
            score += 10
        elif rb_service and target_service in rb_service:
            score += 5
        elif rb_service == 'general' or not rb_service:
            score += 1

        # Alert type matching
        rb_alert_types = [t.lower() for t in runbook.get('alert_types', [])]
        target_alert = alert_type.lower().replace('-', '_')

        if target_alert in rb_alert_types:
            score += 10
        else:
            # Partial matching for alert types
            for rb_type in rb_alert_types:
                if target_alert in rb_type or rb_type in target_alert:
                    score += 6
                    break

        # Severity matching
        if severity:
            rb_severities = runbook.get('severity', [])
            if isinstance(rb_severities, str):
                rb_severities = [rb_severities]
            if severity.lower() in [s.lower() for s in rb_severities]:
                score += 2

        # Tag-based bonus
        tags = [t.lower() for t in runbook.get('tags', [])]
        if target_alert.replace('_', '') in ' '.join(tags):
            score += 1

        return score

    async def find_runbook(
        self,
        service: str,
        alert_type: str,
        severity: Optional[str] = None
    ) -> dict:
        """Find relevant runbooks for a service and alert type.

        Args:
            service: Service name
            alert_type: Alert type
            severity: Alert severity (optional)

        Returns:
            Dict with matched runbooks
        """
        logger.info(f"Finding runbooks for service={service}, alert_type={alert_type}, severity={severity}")

        runbooks = self._load_runbooks()

        if not runbooks:
            return {
                'found': False,
                'message': 'No runbooks available in corpus',
                'runbooks': []
            }

        # Score and rank runbooks
        scored_runbooks = []
        for runbook in runbooks:
            score = self._match_score(runbook, service, alert_type, severity)
            if score > 0:
                scored_runbooks.append({
                    'score': score,
                    'runbook': runbook
                })

        # Sort by score
        scored_runbooks.sort(key=lambda x: x['score'], reverse=True)

        # Return top matches
        top_matches = []
        for item in scored_runbooks[:3]:  # Top 3 matches
            rb = item['runbook']
            top_matches.append({
                'title': rb['title'],
                'service': rb['service'],
                'alert_types': rb['alert_types'],
                'severity': rb['severity'],
                'tags': rb['tags'],
                'path': rb['path'],
                'content': rb['content'],
                'match_score': item['score']
            })

        if not top_matches:
            return {
                'found': False,
                'message': f'No runbooks found for service={service}, alert_type={alert_type}',
                'runbooks': [],
                'suggestions': [
                    'Check if runbooks exist for this service',
                    'Look for general troubleshooting runbooks',
                    'Create a new runbook for this alert type'
                ]
            }

        return {
            'found': True,
            'count': len(top_matches),
            'runbooks': top_matches,
            'best_match': top_matches[0]
        }
