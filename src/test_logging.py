#!/usr/bin/env python3
"""
Simple test script to verify logging configuration.
Run this to see how logs will appear in production.
"""

from src.utils.logging import setup_logging, RequestContext, get_logger

def test_logging():
    """Test the logging setup."""
    # Initialize logging
    setup_logging()
    
    logger = get_logger(__name__)
    
    print("\n" + "="*80)
    print("LOGGING TEST - You should see structured logs below")
    print("="*80 + "\n")
    
    # Test basic logging
    logger.info("Testing basic log message")
    logger.info("Testing log with extras", extra={
        "user_id": 123,
        "action": "test",
        "duration_ms": 45.3
    })
    
    # Test request context
    request_id = RequestContext.start_request("test query about products")
    logger.info("Testing request context", extra={
        "node": "test",
        "some_data": {"key": "value"}
    })
    
    # Test different log levels
    logger.debug("This is a DEBUG message (may not show if LOG_LEVEL=INFO)")
    logger.info("This is an INFO message")
    logger.warning("This is a WARNING message", extra={"warning_code": "W001"})
    
    # Test error logging
    try:
        raise ValueError("This is a test error")
    except Exception as e:
        logger.error("Testing error logging", extra={
            "error_type": "ValueError",
            "context": "test_function"
        }, exc_info=True)
    
    RequestContext.clear()
    
    print("\n" + "="*80)
    print("LOGGING TEST COMPLETE")
    print("="*80 + "\n")
    
    print("\nTo change logging format, set LOG_FORMAT in your .env file:")
    print("  LOG_FORMAT=console  # Human-readable (default)")
    print("  LOG_FORMAT=json     # JSON only (for DB ingestion)")
    print("  LOG_FORMAT=both     # Both formats\n")

if __name__ == "__main__":
    test_logging()

