# Logging System Documentation

## Overview

The Opsfleet LangGraph Agent now has a comprehensive structured logging system that:
- ✅ Tracks execution through all nodes (intent → plan → sqlgen → exec → results → insight → respond)
- ✅ Provides dual output: human-readable console + machine-readable JSON
- ✅ Traces requests end-to-end with unique request IDs
- ✅ Ready for external database ingestion
- ✅ Preserves all information from previous logging

## Quick Start

### 1. Configure Logging

Set environment variables in your `.env` file:

```bash
# Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO

# Output format
# - console: Human-readable text (default)
# - json: Structured JSON only
# - both: Console to stdout, JSON to stderr
LOG_FORMAT=console

# Optional: Write to file
# LOG_FILE=logs/app.log

# Enable request tracing
ENABLE_REQUEST_TRACING=true
```

### 2. Test the Logging

```bash
# Test logging configuration
python -m src.test_logging

# Run a query and see logs
python -m src.dev_single_with_timing
```

## Log Output Formats

### Console Format (Human-Readable)

```
2025-11-04 10:23:45.123 | INFO    | intent          | intent_node starting | query="top products last 30 days" | query_length=28
2025-11-04 10:23:45.125 | INFO    | intent          | intent_node classified | intent="product" | rule="product_keywords" | duration_ms=1.5
2025-11-04 10:23:45.126 | INFO    | plan            | plan_node starting | intent="product" | query="top products last 30 days"
2025-11-04 10:23:58.890 | INFO    | plan            | plan_node LLM refinement completed | llm_duration_ms=13764.2
2025-11-04 10:24:00.123 | INFO    | exec            | exec_node dry_run completed | estimated_bytes=125000
2025-11-04 10:24:08.456 | INFO    | exec            | exec_node query executed | query_duration_ms=7800.5 | row_count=20
```

### JSON Format (DB-Ready)

```json
{
  "timestamp": "2025-11-04T10:23:45.123Z",
  "level": "INFO",
  "logger": "src.nodes.intent",
  "message": "intent_node starting",
  "module": "intent",
  "function": "intent_node",
  "line": 20,
  "request_id": "req_3547f7dc0f42",
  "user_query": "top products last 30 days",
  "node": "intent",
  "query_length": 28
}
```

## What Gets Logged

### All Nodes Log:
- ✅ Entry/exit with timing
- ✅ Key decisions and parameters
- ✅ Errors with full context
- ✅ Request ID for tracing

### Node-Specific Logs:

#### Intent Node
- Matched keywords
- Classification rule used
- Final intent chosen

#### Plan Node
- Template selection
- LLM refinement duration
- Parameter extraction

#### SQLGen Node
- Template ID
- Generated SQL length

#### Exec Node
- Dry-run byte estimate
- Query execution time
- Rows returned
- Retry attempts (if any)

#### Results Node
- Row processing stats
- Aggregation summaries

#### Insight Node
- LLM call duration
- Generated insights count

#### Respond Node
- Final response length

## Request Tracing

Every query gets a unique `request_id` that flows through all nodes:

```python
from src.utils.logging import RequestContext

# Start tracking
request_id = RequestContext.start_request("user query here")

# Request ID automatically added to all logs

# Clean up
RequestContext.clear()
```

## Integration with External Systems

### Send to CloudWatch

```python
# Add to src/utils/logging.py setup_logging()
import watchtower

handler = watchtower.CloudWatchLogHandler()
handler.setFormatter(JSONFormatter())
root_logger.addHandler(handler)
```

### Send to Datadog

```bash
# Set in .env
LOG_FORMAT=json
LOG_FILE=logs/app.log

# Configure Datadog agent to tail logs/app.log
```

### Send to ELK Stack

```bash
# Pipe JSON logs to Logstash
python -m src.main 2>&1 | grep '^{' | logstash -f config.conf
```

### Send to MongoDB

```python
# Custom handler in src/utils/logging.py
class MongoHandler(logging.Handler):
    def emit(self, record):
        log_entry = json.loads(JSONFormatter().format(record))
        mongo_collection.insert_one(log_entry)
```

## Performance Monitoring

The logs automatically track:
- Node execution times
- LLM call durations  
- BigQuery query times
- Total request duration

Example query to find slow nodes (if stored in DB):

```sql
SELECT 
  node,
  AVG(duration_ms) as avg_duration,
  MAX(duration_ms) as max_duration,
  COUNT(*) as call_count
FROM logs
WHERE level = 'INFO' 
  AND message LIKE '%completed'
GROUP BY node
ORDER BY avg_duration DESC;
```

## Troubleshooting

### No logs appearing?

Check your `LOG_LEVEL` setting:
```bash
export LOG_LEVEL=DEBUG  # See everything
export LOG_LEVEL=INFO   # Normal operation
```

### Want to see only errors?

```bash
export LOG_LEVEL=ERROR
```

### JSON logs mixed with console output?

Use `LOG_FORMAT=json` for clean JSON only:
```bash
export LOG_FORMAT=json
python -m src.main > logs.jsonl
```

### Reduce log verbosity?

Set `LOG_LEVEL=WARNING` to only see warnings and errors.

## Development vs Production

### Development (recommended)
```bash
LOG_LEVEL=INFO
LOG_FORMAT=console
```

### Production (recommended)
```bash
LOG_LEVEL=WARNING
LOG_FORMAT=json
LOG_FILE=/var/log/opsfleet/app.log
```

## API

### Get a Logger

```python
from src.utils.logging import get_logger

logger = get_logger(__name__)
logger.info("Message", extra={"key": "value"})
```

### Helper Functions

```python
from src.utils.logging import log_node_entry, log_node_exit, log_error

# Log node entry
log_node_entry(logger, "my_node", {"query": "..."})

# Log node exit
log_node_exit(logger, "my_node", duration_ms=123.4, {"result": "success"})

# Log errors
log_error(logger, "my_node", exception, {"context": "info"})
```

## Examples

See:
- `src/test_logging.py` - Basic logging test
- `src/dev_single_with_timing.py` - Real scenario with logging
- All nodes in `src/nodes/*` - Production usage examples

