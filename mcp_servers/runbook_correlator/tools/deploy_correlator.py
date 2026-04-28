"""Deploy correlator tool - ranks deployments by suspicion score."""

import logging
from datetime import datetime, timedelta
from typing import Optional
import os

logger = logging.getLogger(__name__)


class DeployCorrelator:
    """Correlate deployments with incident timing.

    Analyzes deployment history and ranks deploys by "suspicion score"
    based on temporal correlation with the incident.

    Suspicion scoring factors:
    1. Temporal proximity - how close to incident start
    2. Change magnitude - size of code/config changes
    3. Change type - config changes vs code changes
    4. Historical risk - previous incidents from similar changes
    5. Deployment method - automated vs manual

    In eval mode, loads deploy data from fixtures.
    In live mode, would query deployment APIs (K8s, ArgoCD, etc.)
    """

    def __init__(self):
        """Initialize deploy correlator."""
        self.mode = os.getenv("MODE", "eval")
        logger.info(f"Initialized DeployCorrelator (mode: {self.mode})")

    def _calculate_suspicion_score(
        self,
        deploy: dict,
        incident_start: datetime,
        incident_end: datetime
    ) -> dict:
        """Calculate suspicion score for a deployment.

        Args:
            deploy: Deployment metadata
            incident_start: Incident start time
            incident_end: Incident end time

        Returns:
            Dict with score and breakdown
        """
        score = 0.0
        breakdown = {}

        # Parse deploy time
        deploy_time_str = deploy.get('deployedAt', deploy.get('timestamp'))
        try:
            deploy_time = datetime.fromisoformat(deploy_time_str.replace('Z', '+00:00'))
        except Exception as e:
            logger.warning(f"Failed to parse deploy time: {e}")
            return {'total_score': 0.0, 'breakdown': {}, 'error': 'Invalid timestamp'}

        # 1. Temporal proximity (0-50 points)
        # Deploys right before incident are most suspicious
        time_delta = (incident_start - deploy_time).total_seconds() / 60  # minutes

        if 0 <= time_delta <= 15:  # Within 15 minutes before incident
            temporal_score = 50.0
        elif 15 < time_delta <= 60:  # 15-60 minutes
            temporal_score = 40.0
        elif 60 < time_delta <= 240:  # 1-4 hours
            temporal_score = 30.0
        elif 240 < time_delta <= 1440:  # 4-24 hours
            temporal_score = 15.0
        elif time_delta < 0:  # Deploy happened after incident started
            temporal_score = 5.0
        else:  # More than 24 hours
            temporal_score = 5.0

        score += temporal_score
        breakdown['temporal_proximity'] = {
            'score': temporal_score,
            'minutes_before_incident': max(0, time_delta),
            'explanation': self._temporal_explanation(time_delta)
        }

        # 2. Change magnitude (0-30 points)
        changes = deploy.get('changes', [])
        change_score = 0.0

        if not changes:
            change_score = 5.0  # Unknown changes, moderate suspicion
        else:
            # Score based on number and type of changes
            config_changes = sum(1 for c in changes if 'resources' in c.get('field', '').lower()
                               or 'limits' in c.get('field', '').lower()
                               or 'env' in c.get('field', '').lower())
            code_changes = len(changes) - config_changes

            change_score = min(30.0, config_changes * 10 + code_changes * 5)

        score += change_score
        breakdown['change_magnitude'] = {
            'score': change_score,
            'total_changes': len(changes),
            'config_changes': sum(1 for c in changes if 'resources' in c.get('field', '').lower()),
            'explanation': f"{len(changes)} total changes detected"
        }

        # 3. Change type risk (0-20 points)
        risk_score = 0.0
        risk_patterns = {
            'memory': 15.0,  # Memory changes are risky
            'cpu': 10.0,
            'replicas': 12.0,
            'env': 8.0,
            'image': 7.0,
            'limits': 15.0,
            'requests': 12.0
        }

        risky_changes = []
        for change in changes:
            field = change.get('field', '').lower()
            for pattern, pattern_score in risk_patterns.items():
                if pattern in field:
                    risk_score = max(risk_score, pattern_score)
                    risky_changes.append(pattern)

        score += risk_score
        breakdown['change_type_risk'] = {
            'score': risk_score,
            'risky_patterns': list(set(risky_changes)),
            'explanation': f"High-risk change types: {', '.join(set(risky_changes))}" if risky_changes else "No high-risk patterns"
        }

        # 4. Deployment metadata (0-10 points)
        metadata_score = 0.0

        # Automated deploys might be less tested
        deployed_by = deploy.get('deployedBy', '')
        if 'bot' in deployed_by.lower() or 'auto' in deployed_by.lower():
            metadata_score += 3.0

        # Recent revision (higher number = more recent, potentially less stable)
        revision = deploy.get('revision', 0)
        if revision > 5:
            metadata_score += 2.0

        score += metadata_score
        breakdown['deployment_metadata'] = {
            'score': metadata_score,
            'deployed_by': deployed_by,
            'revision': revision,
            'automated': 'bot' in deployed_by.lower()
        }

        # Normalize to 0-100
        total_score = min(100.0, score)

        return {
            'total_score': round(total_score, 2),
            'breakdown': breakdown,
            'deploy_time': deploy_time.isoformat(),
            'minutes_before_incident': max(0, round(time_delta, 2))
        }

    def _temporal_explanation(self, minutes: float) -> str:
        """Generate human-readable temporal explanation."""
        if minutes < 0:
            return "Deployed after incident started (likely not the cause)"
        elif minutes <= 15:
            return "Deployed immediately before incident (highly suspicious)"
        elif minutes <= 60:
            return "Deployed shortly before incident (suspicious)"
        elif minutes <= 240:
            return "Deployed a few hours before incident (possibly related)"
        elif minutes <= 1440:
            return "Deployed within 24 hours (might be related)"
        else:
            return "Deployed more than 24 hours before (unlikely to be cause)"

    async def correlate_deploys(
        self,
        service: str,
        time_window_start: str,
        time_window_end: str,
        lookback_hours: int = 24
    ) -> dict:
        """Correlate deployments with incident timing.

        Args:
            service: Service name
            time_window_start: Incident start time (ISO 8601)
            time_window_end: Incident end time (ISO 8601)
            lookback_hours: How many hours before incident to search

        Returns:
            Dict with ranked deployments
        """
        logger.info(f"Correlating deploys for service={service}, window={time_window_start} to {time_window_end}")

        try:
            incident_start = datetime.fromisoformat(time_window_start.replace('Z', '+00:00'))
            incident_end = datetime.fromisoformat(time_window_end.replace('Z', '+00:00'))
        except Exception as e:
            return {
                'error': f'Invalid time window format: {e}',
                'service': service
            }

        # In eval mode, load from fixtures
        if self.mode == "eval":
            deploys = await self._load_deploys_from_fixtures(service)
        else:
            # In live mode, would query deployment APIs
            deploys = await self._load_deploys_from_api(service, lookback_hours)

        if not deploys:
            return {
                'service': service,
                'deploys_found': 0,
                'message': f'No deployments found for {service}',
                'ranked_deploys': []
            }

        # Calculate suspicion scores
        scored_deploys = []
        for deploy in deploys:
            suspicion = self._calculate_suspicion_score(deploy, incident_start, incident_end)

            scored_deploys.append({
                'deployment': deploy,
                'suspicion_score': suspicion['total_score'],
                'suspicion_breakdown': suspicion['breakdown'],
                'deploy_time': suspicion['deploy_time'],
                'minutes_before_incident': suspicion['minutes_before_incident']
            })

        # Sort by suspicion score (highest first)
        scored_deploys.sort(key=lambda x: x['suspicion_score'], reverse=True)

        return {
            'service': service,
            'incident_window': {
                'start': time_window_start,
                'end': time_window_end
            },
            'deploys_found': len(scored_deploys),
            'ranked_deploys': scored_deploys,
            'most_suspicious': scored_deploys[0] if scored_deploys else None
        }

    async def _load_deploys_from_fixtures(self, service: str) -> list[dict]:
        """Load deploy data from fixtures (eval mode).

        Args:
            service: Service name

        Returns:
            List of deployment dicts
        """
        # Try to load from MCP mock server fixtures
        try:
            from mcp_servers.registry import get_mcp_server

            registry = get_mcp_server()
            result = registry.call_tool(
                "kubernetes",
                "k8s_get_deployments",
                {"namespace": "default", "deployment_name": service}
            )

            deployments = result.get('deployments', [])
            if not deployments:
                return []

            # Extract deployment history
            deploy_history = []
            for deployment in deployments:
                history = deployment.get('rolloutHistory', [])
                for deploy in history:
                    deploy_history.append(deploy)

            return deploy_history

        except Exception as e:
            logger.warning(f"Failed to load deploys from fixtures: {e}")
            return []

    async def _load_deploys_from_api(self, service: str, lookback_hours: int) -> list[dict]:
        """Load deploy data from live APIs (live mode).

        Args:
            service: Service name
            lookback_hours: Lookback period

        Returns:
            List of deployment dicts
        """
        # TODO: Implement live API integration
        # Would query:
        # - Kubernetes API for deployment history
        # - ArgoCD API for GitOps deployments
        # - CI/CD system APIs (Jenkins, GitHub Actions, etc.)

        logger.warning("Live mode not implemented yet")
        return []
