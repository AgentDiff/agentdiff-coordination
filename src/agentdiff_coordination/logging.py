import logging
import json
import time
import os
import sys
from typing import Any, Dict, Optional, Union
from datetime import datetime
from pathlib import Path

from .config import config

# Default configuration
DEFAULT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DEFAULT_JSON_FORMAT = {
    "timestamp": "%(asctime)s",
    "level": "%(levelname)s",
    "logger": "%(name)s",
    "message": "%(message)s",
    "module": "%(module)s",
    "function": "%(funcName)s",
    "line": "%(lineno)d",
}


class AgentDiffFormatter(logging.Formatter):
    """Custom formatter with JSON support"""

    def __init__(self, use_json: bool = False, include_extra: bool = True):
        self.use_json = use_json
        self.include_extra = include_extra

        if use_json:
            self.base_format = DEFAULT_JSON_FORMAT
            super().__init__()
        else:
            super().__init__(DEFAULT_LOG_FORMAT)

    def format(self, record: logging.LogRecord) -> str:
        if not self.use_json:
            return super().format(record)

        # Create JSON log entry
        log_entry = {}

        # Add standard fields
        for key, format_str in self.base_format.items():
            try:
                log_entry[key] = format_str % record.__dict__
            except (KeyError, ValueError):
                log_entry[key] = None

        # Add AgentDiff data if present
        if self.include_extra and hasattr(record, "agentdiff_data"):
            agent_data = record.agentdiff_data
            if isinstance(agent_data, dict):
                log_entry.update(agent_data)

        return json.dumps(log_entry)


class AgentLogger:
    """Logger for AI agents"""

    def __init__(
        self,
        name: str,
        level: Union[str, int] = "INFO",
        log_file: Optional[str] = None,
        use_json: bool = False,
        console_output: bool = True,
    ):
        self.logger = logging.getLogger(f"agentdiff_coordination.{name}")
        self.logger.setLevel(
            getattr(logging, level.upper()) if isinstance(level, str) else level
        )

        # Clear existing handlers
        self.logger.handlers.clear()

        # Setup formatters
        self.formatter = AgentDiffFormatter(use_json=use_json)

        # Console handler
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(self.formatter)
            self.logger.addHandler(console_handler)

        # File handler
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(self.formatter)
            self.logger.addHandler(file_handler)

        # Prevent propagation to root logger
        self.logger.propagate = False

    def _add_context(self, extra: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Add context information to log entry"""
        context = {
            "timestamp": datetime.utcnow().isoformat(),
            "pid": os.getpid(),
            **extra,
            **kwargs,
        }
        return context

    def info(self, message: str, **kwargs):
        """Log info message with context"""
        extra = self._add_context({}, **kwargs)
        self.logger.info(message, extra={"agentdiff_data": extra})

    def warning(self, message: str, **kwargs):
        """Log warning message with context"""
        extra = self._add_context({}, **kwargs)
        self.logger.warning(message, extra={"agentdiff_data": extra})

    def error(self, message: str, error: Optional[Exception] = None, **kwargs):
        """Log error message with context and exception details"""
        extra = self._add_context({}, **kwargs)

        if error:
            extra.update(
                {
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                    "error_traceback": self._format_exception(error),
                }
            )

        self.logger.error(message, extra={"agentdiff_data": extra})

    def agent_started(self, agent_name: str, **kwargs):
        """Log agent start event"""
        extra = self._add_context(
            {"event_type": "agent_started", "agent_name": agent_name}, **kwargs
        )
        self.logger.info(f"Agent {agent_name} started", extra={"agentdiff_data": extra})

    def agent_completed(self, agent_name: str, duration: float, **kwargs):
        """Log agent completion event"""
        extra = self._add_context(
            {
                "event_type": "agent_completed",
                "agent_name": agent_name,
                "duration": duration,
            },
            **kwargs,
        )
        self.logger.info(
            f"Agent {agent_name} completed in {duration:.3f}s",
            extra={"agentdiff_data": extra},
        )

    def agent_failed(
        self, agent_name: str, error: Exception, duration: float, **kwargs
    ):
        """Log agent failure event"""
        extra = self._add_context(
            {
                "event_type": "agent_failed",
                "agent_name": agent_name,
                "duration": duration,
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
            **kwargs,
        )
        self.logger.error(
            f"Agent {agent_name} failed after {duration:.3f}s: {error}",
            extra={"agentdiff_data": extra},
        )

    def resource_locked(self, resource_name: str, agent_name: str, **kwargs):
        """Log resource lock acquisition"""
        extra = self._add_context(
            {
                "event_type": "resource_locked",
                "resource_name": resource_name,
                "agent_name": agent_name,
            },
            **kwargs,
        )
        self.logger.info(
            f"Resource '{resource_name}' locked by {agent_name}",
            extra={"agentdiff_data": extra},
        )

    def resource_released(
        self, resource_name: str, agent_name: str, duration: float, **kwargs
    ):
        """Log resource lock release"""
        extra = self._add_context(
            {
                "event_type": "resource_released",
                "resource_name": resource_name,
                "agent_name": agent_name,
                "lock_duration": duration,
            },
            **kwargs,
        )
        self.logger.info(
            f"Resource '{resource_name}' released by {agent_name} after {duration:.3f}s",
            extra={"agentdiff_data": extra},
        )

    def cost_tracking(
        self, agent_name: str, cost: float, model: str, tokens: int, **kwargs
    ):
        """Log cost tracking information"""
        extra = self._add_context(
            {
                "event_type": "cost_tracking",
                "agent_name": agent_name,
                "cost": cost,
                "model": model,
                "tokens": tokens,
            },
            **kwargs,
        )
        self.logger.info(
            f"Agent {agent_name} API cost: ${cost:.4f} ({model}, {tokens} tokens)",
            extra={"agentdiff_data": extra},
        )

    def workflow_event(self, event_name: str, event_data: Dict[str, Any], **kwargs):
        """Log workflow event"""
        extra = self._add_context(
            {
                "event_type": "workflow_event",
                "workflow_event_name": event_name,
                "event_data": event_data,
            },
            **kwargs,
        )
        self.logger.info(
            f"Workflow event: {event_name}", extra={"agentdiff_data": extra}
        )

    def _format_exception(self, error: Exception) -> str:
        """Format exception for logging"""
        import traceback

        return "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )


class ProductionMonitor:
    """Production monitoring for agent systems"""

    def __init__(self, logger: AgentLogger):
        self.logger = logger
        self.metrics = {
            "agents_started": 0,
            "agents_completed": 0,
            "agents_failed": 0,
            "total_cost": 0.0,
            "total_duration": 0.0,
            "resource_contentions": 0,
            "workflow_events": 0,
        }
        self.start_time = time.perf_counter()

    def record_agent_start(self, agent_name: str):
        """Record agent start for monitoring"""
        self.metrics["agents_started"] += 1
        self.logger.agent_started(agent_name, metrics=self.metrics.copy())

    def record_agent_completion(
        self, agent_name: str, duration: float, cost: float = 0.0
    ):
        """Record agent completion for monitoring"""
        self.metrics["agents_completed"] += 1
        self.metrics["total_duration"] += duration
        self.metrics["total_cost"] += cost
        self.logger.agent_completed(
            agent_name, duration, cost=cost, metrics=self.metrics.copy()
        )

    def record_agent_failure(self, agent_name: str, error: Exception, duration: float):
        """Record agent failure for monitoring"""
        self.metrics["agents_failed"] += 1
        self.metrics["total_duration"] += duration
        self.logger.agent_failed(
            agent_name, error, duration, metrics=self.metrics.copy()
        )

    def record_resource_contention(self, resource_name: str, wait_time: float):
        """Record resource contention for monitoring"""
        self.metrics["resource_contentions"] += 1
        self.logger.warning(
            f"Resource contention on '{resource_name}' - waited {wait_time:.3f}s",
            resource_name=resource_name,
            wait_time=wait_time,
            metrics=self.metrics.copy(),
        )

    def record_workflow_event(self, event_name: str, event_data: Dict[str, Any]):
        """Record workflow event for monitoring"""
        self.metrics["workflow_events"] += 1
        self.logger.workflow_event(event_name, event_data, metrics=self.metrics.copy())

    def get_summary(self) -> Dict[str, Any]:
        """Get monitoring summary"""
        runtime = time.perf_counter() - self.start_time
        return {
            **self.metrics,
            "runtime_seconds": runtime,
            "success_rate": self.metrics["agents_completed"]
            / max(self.metrics["agents_started"], 1),
            "average_duration": self.metrics["total_duration"]
            / max(self.metrics["agents_completed"], 1),
            "agents_per_minute": (
                (self.metrics["agents_completed"] / runtime) * 60 if runtime > 0 else 0
            ),
        }

    def log_summary(self):
        """Log monitoring summary"""
        summary = self.get_summary()
        self.logger.info("System monitoring summary", **summary)


# Global logger instances
_loggers: Dict[str, AgentLogger] = {}
_monitor: Optional[ProductionMonitor] = None


def get_logger(
    name: str = "coordination",
    level: str = None,
    log_file: str = None,
    use_json: bool = None,
    console_output: bool = None,
) -> AgentLogger:
    """Get or create AgentDiff logger"""
    global _loggers

    if name not in _loggers:
        # Get configuration from environment
        logger_config = {
            "level": level or config.log_level,
            "log_file": log_file or config.log_file,
            "use_json": use_json if use_json is not None else config.log_json,
            "console_output": (
                console_output if console_output is not None else config.log_console
            ),
        }

        _loggers[name] = AgentLogger(name, **logger_config)

    return _loggers[name]


def get_monitor() -> ProductionMonitor:
    """Get global production monitor"""
    global _monitor

    if _monitor is None:
        logger = get_logger("monitor")
        _monitor = ProductionMonitor(logger)

    return _monitor


def configure_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    use_json: bool = False,
    console_output: bool = True,
):
    """Configure global logging settings"""
    global _loggers

    # Clear existing loggers to force reconfiguration
    _loggers.clear()

    # Set environment variables for future logger creation
    os.environ["AGENTDIFF_LOG_LEVEL"] = level
    if log_file:
        os.environ["AGENTDIFF_LOG_FILE"] = log_file
    os.environ["AGENTDIFF_LOG_JSON"] = str(use_json).lower()
    os.environ["AGENTDIFF_LOG_CONSOLE"] = str(console_output).lower()


# Example production configurations
PRODUCTION_CONFIG = {
    "level": "INFO",
    "log_file": "/var/log/agentdiff/coordination.log",
    "use_json": True,
    "console_output": False,
}

DEVELOPMENT_CONFIG = {
    "level": "DEBUG",
    "log_file": None,
    "use_json": False,
    "console_output": True,
}

TESTING_CONFIG = {
    "level": "WARNING",
    "log_file": None,
    "use_json": False,
    "console_output": True,
}
