"""Incident detection daemon for automatic agent triggering.

This daemon monitors Kubernetes events and other signals for incidents,
automatically triggering the AI agent when problems are detected.
"""

import os
import time
import subprocess
import logging
from datetime import datetime, timedelta
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class IncidentDetector:
    """Monitors for incidents and triggers the AI agent."""

    def __init__(
        self,
        poll_interval: int = 30,
        services_to_monitor: Optional[list[str]] = None
    ):
        """Initialize incident detector.

        Args:
            poll_interval: How often to check for incidents (seconds)
            services_to_monitor: List of service names to monitor (None = all)
        """
        self.poll_interval = poll_interval
        self.services_to_monitor = services_to_monitor or ["demo-app"]
        self.last_triggered = {}  # Track when we last triggered for each service
        self.cooldown_period = 300  # Don't re-trigger same service within 5 minutes

    def check_for_incidents(self) -> Optional[dict]:
        """Check Kubernetes for incidents.

        Returns:
            Incident dict if detected, None otherwise
        """
        # Check for OOMKilled pods
        for service in self.services_to_monitor:
            incident = self._check_oom_events(service)
            if incident:
                return incident

            # Could add more checks here:
            # - CrashLoopBackOff
            # - High error rates
            # - Prometheus alerts
            # etc.

        return None

    def _check_oom_events(self, service: str) -> Optional[dict]:
        """Check for OOMKilled events for a service.

        Args:
            service: Service name to check

        Returns:
            Incident dict if OOM detected, None otherwise
        """
        try:
            # Get recent events (last 5 minutes)
            result = subprocess.run(
                [
                    "kubectl", "get", "events",
                    "-n", "default",
                    "--field-selector", "reason=OOMKilling",
                    "-o", "json"
                ],
                capture_output=True,
                text=True,
                check=True
            )

            import json
            events = json.loads(result.stdout).get("items", [])

            # Filter for events related to our service in the last 5 minutes
            recent_oom_events = []
            cutoff_time = datetime.now() - timedelta(minutes=5)

            for event in events:
                involved_object = event.get("involvedObject", {})
                pod_name = involved_object.get("name", "")

                # Check if this pod belongs to our service
                if service in pod_name:
                    event_time_str = event.get("lastTimestamp", "")
                    if event_time_str:
                        # Parse event time (ISO 8601 format)
                        event_time = datetime.fromisoformat(event_time_str.replace('Z', '+00:00'))
                        if event_time.replace(tzinfo=None) > cutoff_time:
                            recent_oom_events.append(event)

            if recent_oom_events:
                # Check cooldown
                last_trigger = self.last_triggered.get(service, 0)
                if time.time() - last_trigger < self.cooldown_period:
                    logger.info(f"OOM detected for {service} but still in cooldown period")
                    return None

                logger.warning(f"🚨 OOM incident detected for {service}!")
                logger.info(f"Found {len(recent_oom_events)} OOMKilled events in last 5 minutes")

                return {
                    "service": service,
                    "type": "oomkilled",
                    "severity": "high",
                    "events": recent_oom_events,
                    "detected_at": datetime.now()
                }

        except Exception as e:
            logger.error(f"Error checking OOM events: {e}")

        return None

    def trigger_agent(self, incident: dict):
        """Trigger the AI agent to investigate an incident.

        Args:
            incident: Incident details
        """
        service = incident["service"]
        logger.info(f"🤖 Triggering AI agent for {service} incident...")

        try:
            # Run the agent in a subprocess
            result = subprocess.run(
                ["python", "-m", "agent.graph"],
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )

            if result.returncode == 0:
                logger.info(f"✅ Agent completed successfully for {service}")
                self.last_triggered[service] = time.time()
            else:
                logger.error(f"❌ Agent failed for {service}")
                logger.error(f"Error output: {result.stderr[:500]}")

        except subprocess.TimeoutExpired:
            logger.error(f"⏱️  Agent timed out after 10 minutes for {service}")
        except Exception as e:
            logger.error(f"❌ Error running agent: {e}")

    def run(self):
        """Run the monitoring loop."""
        logger.info("🔍 Starting incident detector...")
        logger.info(f"Monitoring services: {', '.join(self.services_to_monitor)}")
        logger.info(f"Poll interval: {self.poll_interval} seconds")
        logger.info("Press Ctrl+C to stop\n")

        try:
            while True:
                # Check for incidents
                incident = self.check_for_incidents()

                if incident:
                    logger.warning(f"🚨 INCIDENT DETECTED: {incident['type']} in {incident['service']}")
                    self.trigger_agent(incident)
                else:
                    logger.debug(f"✓ No incidents detected at {datetime.now().strftime('%H:%M:%S')}")

                # Wait before next check
                time.sleep(self.poll_interval)

        except KeyboardInterrupt:
            logger.info("\n👋 Shutting down incident detector...")


def main():
    """Main entry point."""
    detector = IncidentDetector(
        poll_interval=30,  # Check every 30 seconds
        services_to_monitor=["demo-app"]  # Add more services here
    )
    detector.run()


if __name__ == "__main__":
    main()
