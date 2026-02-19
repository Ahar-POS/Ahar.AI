"""
Data Loader Service

Loads and filters data from lexis_test_data for report generation.
Handles orders, daily aggregates, inventory, and other data sources.

Cost optimization:
- All data filtering happens server-side (0 LLM cost)
- Only filtered data is sent to Skills API
- Caching support for frequently accessed data
"""

import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)


class DataLoader:
    """Load and filter restaurant data from Excel files"""

    def __init__(self, data_path: Path):
        """
        Initialize DataLoader

        Args:
            data_path: Path to lexis_test_data directory
        """
        self.data_path = Path(data_path)
        self._validate_data_path()

        # Cache for loaded data (optional - can add TTL if needed)
        self._cache = {}

    def _validate_data_path(self):
        """Validate data directory exists"""
        if not self.data_path.exists():
            raise ValueError(f"Data path does not exist: {self.data_path}")

        if not self.data_path.is_dir():
            raise ValueError(f"Data path is not a directory: {self.data_path}")

        logger.info(f"DataLoader initialized with path: {self.data_path}")

    def _load_excel(self, filename: str, cache_key: Optional[str] = None) -> pd.DataFrame:
        """
        Load Excel file with optional caching

        Args:
            filename: Excel filename (e.g., "orders.xlsx")
            cache_key: Optional cache key for this data

        Returns:
            DataFrame with loaded data

        Raises:
            FileNotFoundError: If file doesn't exist
            Exception: If file can't be loaded
        """
        file_path = self.data_path / filename

        if not file_path.exists():
            raise FileNotFoundError(f"Data file not found: {file_path}")

        # Check cache
        if cache_key and cache_key in self._cache:
            logger.info(f"Loading {filename} from cache")
            return self._cache[cache_key].copy()

        # Load from disk
        logger.info(f"Loading {filename} from disk")
        try:
            df = pd.read_excel(file_path)

            # Cache if key provided
            if cache_key:
                self._cache[cache_key] = df.copy()

            logger.info(f"Loaded {len(df)} rows from {filename}")
            return df

        except Exception as e:
            logger.error(f"Failed to load {filename}: {e}")
            raise

    def get_orders_filtered(
        self,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Get orders filtered by date range

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame with filtered orders

        Raises:
            ValueError: If dates are invalid
        """
        # Load orders (cached)
        df = self._load_excel("orders.xlsx", cache_key="orders")

        # Convert Order_Date to datetime
        df['Order_Date'] = pd.to_datetime(df['Order_Date'])

        # Convert filter dates to datetime
        try:
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
        except Exception as e:
            raise ValueError(f"Invalid date format: {e}")

        # Filter by date range
        mask = (df['Order_Date'] >= start_dt) & (df['Order_Date'] <= end_dt)
        filtered = df[mask].copy()

        logger.info(
            f"Filtered orders: {len(filtered)} of {len(df)} "
            f"({start_date} to {end_date})"
        )

        # Convert date back to string for CSV export
        filtered['Order_Date'] = filtered['Order_Date'].dt.strftime('%Y-%m-%d')

        return filtered

    def get_daily_aggregates(
        self,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Get daily aggregates filtered by date range

        Future use for daily summary reports.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame with filtered daily aggregates
        """
        df = self._load_excel("daily_aggregates.xlsx", cache_key="daily_agg")

        df['Date'] = pd.to_datetime(df['Date'])
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)

        mask = (df['Date'] >= start_dt) & (df['Date'] <= end_dt)
        filtered = df[mask].copy()

        filtered['Date'] = filtered['Date'].dt.strftime('%Y-%m-%d')

        logger.info(f"Filtered daily_aggregates: {len(filtered)} rows")
        return filtered

    def get_raw_material_inventory(self) -> pd.DataFrame:
        """
        Get raw material inventory data

        Future use for inventory reports and COGS calculation.

        Returns:
            DataFrame with inventory data
        """
        df = self._load_excel("raw_material_inventory.xlsx", cache_key="inventory")
        logger.info(f"Loaded inventory: {len(df)} materials")
        return df

    def get_stock_movement_log(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get stock movement log, optionally filtered by date

        Future use for COGS tracking and inventory analysis.

        Args:
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)

        Returns:
            DataFrame with stock movements
        """
        df = self._load_excel("stock_movement_log.xlsx", cache_key="stock_movement")

        if start_date and end_date:
            df['Date'] = pd.to_datetime(df['Date'])
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)

            mask = (df['Date'] >= start_dt) & (df['Date'] <= end_dt)
            df = df[mask].copy()

            df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')

        logger.info(f"Loaded stock movements: {len(df)} records")
        return df

    def get_customer_dimension(self) -> pd.DataFrame:
        """
        Get customer dimension data

        Future use for customer analysis reports.

        Returns:
            DataFrame with customer data
        """
        df = self._load_excel("customer_dimension.xlsx", cache_key="customers")
        logger.info(f"Loaded customers: {len(df)} records")
        return df

    def clear_cache(self):
        """Clear the data cache"""
        self._cache = {}
        logger.info("Data cache cleared")

    def get_data_info(self) -> dict:
        """
        Get info about available data files

        Returns:
            Dictionary with file names and row counts
        """
        info = {}

        files = [
            "orders.xlsx",
            "daily_aggregates.xlsx",
            "raw_material_inventory.xlsx",
            "stock_movement_log.xlsx",
            "customer_dimension.xlsx"
        ]

        for filename in files:
            try:
                df = self._load_excel(filename)
                info[filename] = {
                    "rows": len(df),
                    "columns": len(df.columns),
                    "size_mb": round((df.memory_usage(deep=True).sum() / 1024 / 1024), 2)
                }
            except FileNotFoundError:
                info[filename] = {"error": "File not found"}
            except Exception as e:
                info[filename] = {"error": str(e)}

        return info
