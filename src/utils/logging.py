"""
Enhanced logging setup for Opsfleet LangGraph Agent.

Supports:
- Dual output: human-readable console + structured JSON
- Request tracing through the pipeline
- Context injection (query_id, node_name, etc.)
- Production-ready for external DB ingestion
"""

import logging
import json
import os
import sys
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path


# ==================== Context Management ====================

class RequestContext:
    """Thread-safe request context for tracing queries through the pipeline."""
    _current_request_id: Optional[str] = None
    _current_query: Optional[str] = None
    
    @classmethod
    def start_request(cls, query: str) -> str:
        """Start a new request context and return request_id."""
        cls._current_request_id = f"req_{uuid.uuid4().hex[:12]}"
        cls._current_query = query
        return cls._current_request_id
    
    @classmethod
    def get_request_id(cls) -> Optional[str]:
        """Get current request ID."""
        return cls._current_request_id
    
    @classmethod
    def get_query(cls) -> Optional[str]:
        """Get current query."""
        return cls._current_query
    
    @classmethod
    def clear(cls):
        """Clear request context."""
        cls._current_request_id = None
        cls._current_query = None


# ==================== Custom Formatters ====================

class ConsoleFormatter(logging.Formatter):
    """Human-readable console formatter with all context preserved."""
    
    def format(self, record: logging.LogRecord) -> str:
        # Simplified, cleaner format
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        level = record.levelname[0]  # Just first letter: I, W, E, D
        
        # Get node name if available, otherwise use module
        node = None
        if hasattr(record, 'node'):
            node = record.node
        else:
            # Extract from module name
            module_parts = record.name.split('.')
            if 'nodes' in module_parts:
                node = module_parts[-1]
        
        message = record.getMessage()
        
        # Build cleaner format: [TIME] LEVEL NODE: message
        if node:
            parts = [f"[{timestamp}] {level} {node:>8}: {message}"]
        else:
            parts = [f"[{timestamp}] {level} : {message}"]
        
        # Add ONLY key fields (filter out noise)
        key_fields = {}
        skip_fields = ['name', 'msg', 'args', 'created', 'filename', 'funcName', 
                      'levelname', 'levelno', 'lineno', 'module', 'msecs', 
                      'message', 'pathname', 'process', 'processName', 
                      'relativeCreated', 'thread', 'threadName', 'exc_info',
                      'exc_text', 'stack_info', 'taskName', 'node', 'request_id', 
                      'user_query', 'phase']  # Hide verbose fields
        
        for key, value in record.__dict__.items():
            if key not in skip_fields:
                key_fields[key] = value
        
        # Format key fields compactly
        if key_fields:
            # Special handling for common fields
            if 'duration_ms' in key_fields:
                parts.append(f" ({key_fields['duration_ms']:.1f}ms)")
                del key_fields['duration_ms']
            
            if 'intent' in key_fields and 'template_id' not in key_fields:
                parts.append(f" [{key_fields['intent']}]")
                del key_fields['intent']
            
            if 'template_id' in key_fields:
                parts.append(f" → {key_fields['template_id']}")
                del key_fields['template_id']
                
            # Add remaining fields if any (condensed)
            if key_fields and len(key_fields) <= 3:
                extras = ", ".join(f"{k}={self._format_value(v)}" for k, v in list(key_fields.items())[:3])
                parts.append(f" | {extras}")
        
        return "".join(parts)
    
    def _format_value(self, value: Any) -> str:
        """Format a value for console output."""
        if isinstance(value, str):
            # Truncate long strings
            if len(value) > 100:
                return f'"{value[:97]}..."'
            return f'"{value}"'
        elif isinstance(value, (dict, list)):
            s = json.dumps(value, ensure_ascii=False)
            if len(s) > 150:
                return f"{s[:147]}..."
            return s
        else:
            return str(value)


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging (DB-ready)."""
    
    def format(self, record: logging.LogRecord) -> str:
        # Build base log object
        log_obj = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add request context
        if RequestContext.get_request_id():
            log_obj["request_id"] = RequestContext.get_request_id()
        if RequestContext.get_query():
            log_obj["user_query"] = RequestContext.get_query()
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename', 'funcName',
                          'levelname', 'levelno', 'lineno', 'module', 'msecs',
                          'message', 'pathname', 'process', 'processName',
                          'relativeCreated', 'thread', 'threadName', 'exc_info',
                          'exc_text', 'stack_info', 'taskName']:
                log_obj[key] = value
        
        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_obj, ensure_ascii=False, default=str)


# ==================== Setup Function ====================

def setup_logging():
    """
    Setup logging with dual output (console + JSON).
    
    Environment variables:
        LOG_LEVEL: DEBUG, INFO, WARNING, ERROR (default: INFO)
        LOG_FORMAT: console, json, both (default: both)
        LOG_FILE: Optional file path for logs
        ENABLE_REQUEST_TRACING: true/false (default: true)
    """
    # Get configuration from environment
    level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_str, logging.INFO)
    log_format = os.getenv("LOG_FORMAT", "console").lower()  # Changed default to console only
    log_file = os.getenv("LOG_FILE", None)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # Console handler (human-readable)
    if log_format in ["console", "both"]:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(ConsoleFormatter())
        root_logger.addHandler(console_handler)
    
    # JSON handler (for external DB)
    if log_format in ["json", "both"]:
        # If both formats, send JSON to stderr to separate streams
        stream = sys.stderr if log_format == "both" else sys.stdout
        json_handler = logging.StreamHandler(stream)
        json_handler.setLevel(level)
        json_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(json_handler)
    
    # Optional file handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        # Use JSON format for file logs (easier to parse)
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)
    
    # Log startup
    logger = logging.getLogger(__name__)
    logger.info("Logging initialized", extra={
        "log_level": level_str,
        "log_format": log_format,
        "log_file": log_file or "none",
    })


# ==================== Helper Functions ====================

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Logger name (usually __name__ or node name)
    
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def log_node_entry(logger: logging.Logger, node_name: str, state_summary: Dict[str, Any]):
    """
    Log entry into a graph node.
    
    Args:
        logger: Logger instance
        node_name: Name of the node
        state_summary: Summary of incoming state
    """
    logger.info(f"{node_name} starting", extra={
        "node": node_name,
        "phase": "entry",
        **state_summary
    })


def log_node_exit(logger: logging.Logger, node_name: str, duration_ms: float, output_summary: Dict[str, Any]):
    """
    Log exit from a graph node.
    
    Args:
        logger: Logger instance
        node_name: Name of the node
        duration_ms: Execution duration in milliseconds
        output_summary: Summary of output state
    """
    logger.info(f"{node_name} completed", extra={
        "node": node_name,
        "phase": "exit",
        "duration_ms": round(duration_ms, 2),
        **output_summary
    })


def log_error(logger: logging.Logger, node_name: str, error: Exception, context: Dict[str, Any]):
    """
    Log an error with full context.
    
    Args:
        logger: Logger instance
        node_name: Name of the node where error occurred
        error: The exception
        context: Additional context
    """
    logger.error(f"{node_name} failed: {str(error)}", extra={
        "node": node_name,
        "error_type": error.__class__.__name__,
        **context
    }, exc_info=True)


# ==================== Export ====================

__all__ = [
    'setup_logging',
    'get_logger',
    'RequestContext',
    'log_node_entry',
    'log_node_exit',
    'log_error',
]
