"""
Data Loader Service

Loads and filters data from new_test_data (CSV) or MongoDB for report generation.
Handles orders, inventory, and other data sources.

Supports both NEW schema (CSV) and OLD schema (Excel) for backward compatibility.

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
    """Load and filter restaurant data from CSV files (new schema) or Excel (old schema)"""

    def __init__(self, data_path: Path):
        """
        Initialize DataLoader

        Args:
            data_path: Path to data directory (new_test_data or lexis_test_data)
        """
        self.data_path = Path(data_path)
        self._validate_data_path()

        # Cache for loaded data (optional - can add TTL if needed)
        self._cache = {}

        # Detect if using new CSV format or old Excel format
        self.use_csv = (self.data_path / "orders.csv").exists()
        logger.info(f"DataLoader using {'CSV (new schema)' if self.use_csv else 'Excel (old schema)'}")

    def _validate_data_path(self):
        """Validate data directory exists"""
        if not self.data_path.exists():
            raise ValueError(f"Data path does not exist: {self.data_path}")

        if not self.data_path.is_dir():
            raise ValueError(f"Data path is not a directory: {self.data_path}")

        logger.info(f"DataLoader initialized with path: {self.data_path}")

    def _load_file(self, filename: str, cache_key: Optional[str] = None) -> pd.DataFrame:
        """
        Load data file (CSV or Excel) with optional caching

        Args:
            filename: Filename without extension (e.g., "orders")
            cache_key: Optional cache key for this data

        Returns:
            DataFrame with loaded data

        Raises:
            FileNotFoundError: If file doesn't exist
            Exception: If file can't be loaded
        """
        # Check cache first
        if cache_key and cache_key in self._cache:
            logger.info(f"Loading {filename} from cache")
            return self._cache[cache_key].copy()

        # Try CSV first, then Excel
        csv_path = self.data_path / f"{filename}.csv"
        xlsx_path = self.data_path / f"{filename}.xlsx"

        if csv_path.exists():
            file_path = csv_path
            loader = pd.read_csv
        elif xlsx_path.exists():
            file_path = xlsx_path
            loader = pd.read_excel
        else:
            raise FileNotFoundError(f"Data file not found: {filename} (.csv or .xlsx)")

        # Load from disk
        logger.info(f"Loading {file_path.name} from disk")
        try:
            df = loader(file_path)

            # Cache if key provided
            if cache_key:
                self._cache[cache_key] = df.copy()

            logger.info(f"Loaded {len(df)} rows from {file_path.name}")
            return df

        except Exception as e:
            logger.error(f"Failed to load {file_path.name}: {e}")
            raise

    def _normalize_orders_schema(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize orders DataFrame to consistent schema

        Maps new schema (order_date, total_amount) to old schema (Order_Date, Total_INR)
        for backward compatibility with profit-analysis skill.

        Args:
            df: Raw orders DataFrame

        Returns:
            Normalized DataFrame with old-style column names
        """
        df = df.copy()

        # Map new column names to old column names
        column_mapping = {
            'order_date': 'Order_Date',
            'order_time': 'Order_Time',
            'order_hour': 'Hour',
            'order_weekday': 'Day_of_Week',
            'is_weekend': 'Is_Weekend',
            'is_holiday': 'Is_Holiday',
            'holiday_name': 'Holiday_Name',
            'order_type': 'Order_Channel',  # Map order_type to Order_Channel
            'total_amount': 'Total_INR',  # Amount in paise → INR
            'status': 'Order_Status',
        }

        # Rename columns if they exist in new schema
        for new_col, old_col in column_mapping.items():
            if new_col in df.columns:
                df.rename(columns={new_col: old_col}, inplace=True)

        # Convert total_amount from paise to INR (if needed)
        if 'Total_INR' in df.columns and df['Total_INR'].max() > 100000:
            # Values are in paise, convert to INR
            df['Total_INR'] = df['Total_INR'] / 100

        # Add missing columns with defaults (for profit-analysis compatibility)
        if 'Promo_Discount_INR' not in df.columns:
            df['Promo_Discount_INR'] = 0
        if 'Item_Discount_INR' not in df.columns:
            df['Item_Discount_INR'] = 0
        if 'Tax_GST_INR' not in df.columns:
            # Estimate tax as 5% of total (if not present)
            df['Tax_GST_INR'] = df['Total_INR'] * 0.05
        if 'Delivery_Fee_INR' not in df.columns:
            df['Delivery_Fee_INR'] = 0
        if 'Packaging_Charge_INR' not in df.columns:
            df['Packaging_Charge_INR'] = 0

        # Ensure Order_Date is datetime
        if 'Order_Date' in df.columns:
            df['Order_Date'] = pd.to_datetime(df['Order_Date'])

        return df

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
        df = self._load_file("orders", cache_key="orders")

        # Normalize schema (new → old)
        df = self._normalize_orders_schema(df)

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

        Note: daily_aggregates may not exist in new_test_data.
        Returns empty DataFrame if file not found.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame with filtered daily aggregates
        """
        try:
            df = self._load_file("daily_aggregates", cache_key="daily_agg")

            df['Date'] = pd.to_datetime(df['Date'])
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)

            mask = (df['Date'] >= start_dt) & (df['Date'] <= end_dt)
            filtered = df[mask].copy()

            filtered['Date'] = filtered['Date'].dt.strftime('%Y-%m-%d')

            logger.info(f"Filtered daily_aggregates: {len(filtered)} rows")
            return filtered

        except FileNotFoundError:
            logger.warning("daily_aggregates file not found, returning empty DataFrame")
            return pd.DataFrame()

    def get_raw_material_inventory(self) -> pd.DataFrame:
        """
        Get raw material inventory data

        Args:
            df: Raw inventory DataFrame

        Returns:
            Normalized DataFrame with old-style column names
        """
        df = self._load_file("raw_material_inventory", cache_key="inventory")

        # Normalize schema if needed (new schema already uses snake_case which is fine)
        # But we may need to handle unit conversion for display
        logger.info(f"Loaded inventory: {len(df)} materials")
        return df

    def get_stock_movement_log(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get stock movement log, optionally filtered by date

        Args:
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)

        Returns:
            DataFrame with stock movements
        """
        df = self._load_file("stock_movement_log", cache_key="stock_movement")

        if start_date and end_date:
            # Check which date column exists
            date_col = None
            if 'movement_date' in df.columns:
                date_col = 'movement_date'
            elif 'Date' in df.columns:
                date_col = 'Date'

            if date_col:
                df[date_col] = pd.to_datetime(df[date_col])
                start_dt = pd.to_datetime(start_date)
                end_dt = pd.to_datetime(end_date)

                mask = (df[date_col] >= start_dt) & (df[date_col] <= end_dt)
                df = df[mask].copy()

                df[date_col] = df[date_col].dt.strftime('%Y-%m-%d')

                logger.info(f"Filtered stock_movement_log: {len(df)} rows")

        return df


# Singleton instance
_data_loader = None


def get_data_loader(data_path: Path) -> DataLoader:
    """Get or create DataLoader instance"""
    global _data_loader
    if _data_loader is None:
        _data_loader = DataLoader(data_path)
    return _data_loader
