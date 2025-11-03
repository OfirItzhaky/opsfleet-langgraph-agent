"""
BigQuery helper: dry-run, safe execute with byte cap, and optional pagination.

Builds on the existing BigQueryRunner in src/clients/bq_client.py.
"""

from __future__ import annotations
import logging
import time
from typing import Optional, Iterator
import pandas as pd
from google.cloud import bigquery
from google.api_core import exceptions as gex

from .bq_client import BigQueryRunner


DEFAULT_MAX_BYTES = 1_000_000_000  # 1 GB cap for safety
DEFAULT_PREVIEW_LIMIT = 500        # cap returned rows in execute()


class BQHelper:
    def __init__(
            self,
            project_id: Optional[str] = None,
            dataset_id: Optional[str] = "bigquery-public-data.thelook_ecommerce",
            max_bytes_scanned: int = DEFAULT_MAX_BYTES,
            preview_limit: int = DEFAULT_PREVIEW_LIMIT,
            client: Optional["bigquery.Client"] = None,
            runner: Optional[BigQueryRunner] = None,
    ) -> None:
        self.max_bytes_scanned = int(max_bytes_scanned)
        self.preview_limit = int(preview_limit)
        self._dataset_id = dataset_id

        if client is not None:
            # Direct client injection (tests)
            self.client = client
            self.runner = runner or BigQueryRunner(project_id=project_id, dataset_id=dataset_id)
            self.runner.client = self.client
        elif runner is not None:
            # Runner injection (advanced tests)
            self.runner = runner
            self.client = runner.client
        else:
            # Normal path (real environment)
            self.runner = BigQueryRunner(project_id=project_id, dataset_id=dataset_id)
            self.client = self.runner.client

    def dry_run(self, sql: str) -> int:
        """Return estimated bytes scanned. Does not execute the query."""
        job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=True)
        job = self.client.query(sql, job_config=job_config)
        est = int(job.total_bytes_processed or 0)
        logging.info(f"Dry-run estimate: {est:,} bytes")
        return est

    def execute_safe(self, sql: str, *, preview_limit: Optional[int] = None) -> pd.DataFrame:
        """
        Dry-run first; if under cap, execute and return a small preview DataFrame.
        """
        estimate = self.dry_run(sql)
        if estimate > self.max_bytes_scanned:
            raise ValueError(
                f"Query would scan {estimate:,} bytes, above cap {self.max_bytes_scanned:,}. "
                "Reduce date range or add filters."
            )

        limit = self.preview_limit if preview_limit is None else int(preview_limit)
        # Wrap user SQL with an outer LIMIT to keep the preview small, unless it already ends with LIMIT.
        sql_lc = sql.strip().lower()
        if not sql_lc.endswith("limit") and " limit " not in sql_lc[-30:]:
            safe_sql = f"SELECT * FROM ({sql}) AS _t LIMIT {limit}"
        else:
            safe_sql = sql

        return self._execute_with_backoff(safe_sql)

    # ---------------------------- Pagination ------------------------------ #
    def execute_paged(self, sql: str, page_size: int = 10_000) -> Iterator[pd.DataFrame]:
        """
        Execute and yield results in pages. Use when you truly need many rows.
        """
        estimate = self.dry_run(sql)
        if estimate > self.max_bytes_scanned:
            raise ValueError(
                f"Query would scan {estimate:,} bytes, above cap {self.max_bytes_scanned:,}."
            )

        job_config = bigquery.QueryJobConfig(use_query_cache=True)
        job = self.client.query(sql, job_config=job_config)
        it = job.result(page_size=page_size)
        for page in it.pages:
            yield page.to_dataframe()

    # ------------------------ Internal backoff exec ------------------------ #
    def _execute_with_backoff(self, sql: str, retries: int = 3, base_delay: float = 1.0) -> pd.DataFrame:
        attempt = 0
        while True:
            try:
                return self.runner.execute_query(sql)
            except (gex.Forbidden, gex.TooManyRequests, gex.ResourceExhausted) as e:
                attempt += 1
                if attempt > retries:
                    logging.error("Exceeded retry attempts.")
                    raise
                sleep_s = base_delay * (2 ** (attempt - 1))
                logging.warning(f"{e.__class__.__name__}: retrying in {sleep_s:.1f}s (attempt {attempt}/{retries})")
                time.sleep(sleep_s)
            except Exception:
                # Surface unexpected errors immediately
                raise
