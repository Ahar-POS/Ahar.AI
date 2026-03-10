"""
Encoders for Categorical Features in ML Models

Provides encoding strategies for categorical features like item_name.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class ItemTargetEncoder:
    """
    Target encoder for item_name feature

    Encodes each item as its average historical demand.
    Handles unseen items with global mean.

    This approach works well with tree-based models like XGBoost
    and avoids the dimensionality explosion of one-hot encoding.

    Example:
        encoder = ItemTargetEncoder()
        df_train = encoder.fit_transform(df_train, 'item_name', 'qty')
        df_test = encoder.transform(df_test, 'item_name')
    """

    def __init__(self):
        self.item_means_: Dict[str, float] = {}
        self.global_mean_: Optional[float] = None
        self.n_items_: int = 0

    def fit(
        self,
        df: pd.DataFrame,
        item_col: str = 'item_name',
        target_col: str = 'qty'
    ) -> 'ItemTargetEncoder':
        """
        Calculate mean target per item

        Args:
            df: DataFrame with item_col and target_col
            item_col: Column name for item identifier
            target_col: Column name for target variable

        Returns:
            self (for method chaining)
        """
        if item_col not in df.columns:
            raise ValueError(f"Column '{item_col}' not found in DataFrame")

        if target_col not in df.columns:
            raise ValueError(f"Column '{target_col}' not found in DataFrame")

        # Calculate per-item means
        self.item_means_ = df.groupby(item_col)[target_col].mean().to_dict()

        # Calculate global mean (for unseen items)
        self.global_mean_ = float(df[target_col].mean())

        self.n_items_ = len(self.item_means_)

        logger.info(f"Fitted ItemTargetEncoder on {self.n_items_} items")
        logger.info(f"  Global mean: {self.global_mean_:.2f}")

        # Show top 5 items by mean
        top_items = sorted(
            self.item_means_.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        logger.info("  Top 5 items by average demand:")
        for item, mean_val in top_items:
            logger.info(f"    {item[:40]:40s} {mean_val:6.2f}")

        return self

    def transform(
        self,
        df: pd.DataFrame,
        item_col: str = 'item_name'
    ) -> pd.DataFrame:
        """
        Transform item_name to encoded values

        Args:
            df: DataFrame with item_col
            item_col: Column name for item identifier

        Returns:
            DataFrame with new column 'item_encoded'
        """
        if self.global_mean_ is None:
            raise ValueError("Encoder not fitted. Call fit() first.")

        if item_col not in df.columns:
            raise ValueError(f"Column '{item_col}' not found in DataFrame")

        df = df.copy()

        # Map item to its mean (or global mean if unseen)
        df['item_encoded'] = df[item_col].map(self.item_means_).fillna(self.global_mean_)

        # Count unseen items
        n_unseen = df[item_col].map(self.item_means_).isna().sum()
        if n_unseen > 0:
            unseen_items = df[df[item_col].map(self.item_means_).isna()][item_col].unique()
            logger.warning(f"Encoded {n_unseen} unseen items with global mean ({self.global_mean_:.2f})")
            logger.warning(f"  Unseen items: {', '.join(unseen_items[:5])}")

        return df

    def fit_transform(
        self,
        df: pd.DataFrame,
        item_col: str = 'item_name',
        target_col: str = 'qty'
    ) -> pd.DataFrame:
        """Fit and transform in one step"""
        self.fit(df, item_col, target_col)
        return self.transform(df, item_col)

    def save(self, filepath: str):
        """
        Save encoder to JSON

        Args:
            filepath: Path to save encoder (will create parent dirs if needed)
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        encoder_dict = {
            'item_means': self.item_means_,
            'global_mean': self.global_mean_,
            'n_items': self.n_items_
        }

        with open(filepath, 'w') as f:
            json.dump(encoder_dict, f, indent=2)

        logger.info(f"Saved ItemTargetEncoder to {filepath}")

    @classmethod
    def load(cls, filepath: str) -> 'ItemTargetEncoder':
        """
        Load encoder from JSON

        Args:
            filepath: Path to encoder JSON file

        Returns:
            Loaded ItemTargetEncoder instance
        """
        with open(filepath, 'r') as f:
            encoder_dict = json.load(f)

        encoder = cls()
        encoder.item_means_ = encoder_dict['item_means']
        encoder.global_mean_ = encoder_dict['global_mean']
        encoder.n_items_ = encoder_dict.get('n_items', len(encoder.item_means_))

        logger.info(f"Loaded ItemTargetEncoder from {filepath}")
        logger.info(f"  {encoder.n_items_} items, global mean: {encoder.global_mean_:.2f}")

        return encoder

    def get_encoding(self, item_name: str) -> float:
        """
        Get encoding value for a single item

        Args:
            item_name: Name of item to encode

        Returns:
            Encoded value (item mean or global mean if unseen)
        """
        if self.global_mean_ is None:
            raise ValueError("Encoder not fitted. Call fit() first.")

        return self.item_means_.get(item_name, self.global_mean_)


class OneHotItemEncoder:
    """
    One-hot encoder for item_name feature

    Alternative to target encoding. Creates binary features for each item.
    More features but no risk of target leakage.

    Example:
        encoder = OneHotItemEncoder()
        df_train = encoder.fit_transform(df_train, 'item_name')
        df_test = encoder.transform(df_test, 'item_name')
    """

    def __init__(self, max_items: int = 100):
        """
        Args:
            max_items: Maximum number of items to encode (keeps top N by frequency)
        """
        self.max_items = max_items
        self.items_: list = []
        self.n_items_: int = 0

    def fit(
        self,
        df: pd.DataFrame,
        item_col: str = 'item_name'
    ) -> 'OneHotItemEncoder':
        """
        Fit encoder on items in DataFrame

        Args:
            df: DataFrame with item_col
            item_col: Column name for item identifier

        Returns:
            self (for method chaining)
        """
        if item_col not in df.columns:
            raise ValueError(f"Column '{item_col}' not found in DataFrame")

        # Get top items by frequency
        item_counts = df[item_col].value_counts()
        self.items_ = item_counts.head(self.max_items).index.tolist()
        self.n_items_ = len(self.items_)

        logger.info(f"Fitted OneHotItemEncoder on {self.n_items_} items")

        return self

    def transform(
        self,
        df: pd.DataFrame,
        item_col: str = 'item_name'
    ) -> pd.DataFrame:
        """
        Transform item_name to one-hot encoded features

        Args:
            df: DataFrame with item_col
            item_col: Column name for item identifier

        Returns:
            DataFrame with binary item_* columns
        """
        if not self.items_:
            raise ValueError("Encoder not fitted. Call fit() first.")

        if item_col not in df.columns:
            raise ValueError(f"Column '{item_col}' not found in DataFrame")

        df = df.copy()

        # Create binary features for each item
        for item in self.items_:
            col_name = f"item_{item.lower().replace(' ', '_')[:30]}"
            df[col_name] = (df[item_col] == item).astype(int)

        return df

    def fit_transform(
        self,
        df: pd.DataFrame,
        item_col: str = 'item_name'
    ) -> pd.DataFrame:
        """Fit and transform in one step"""
        self.fit(df, item_col)
        return self.transform(df, item_col)

    def save(self, filepath: str):
        """Save encoder to JSON"""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        encoder_dict = {
            'items': self.items_,
            'n_items': self.n_items_,
            'max_items': self.max_items
        }

        with open(filepath, 'w') as f:
            json.dump(encoder_dict, f, indent=2)

        logger.info(f"Saved OneHotItemEncoder to {filepath}")

    @classmethod
    def load(cls, filepath: str) -> 'OneHotItemEncoder':
        """Load encoder from JSON"""
        with open(filepath, 'r') as f:
            encoder_dict = json.load(f)

        encoder = cls(max_items=encoder_dict['max_items'])
        encoder.items_ = encoder_dict['items']
        encoder.n_items_ = encoder_dict['n_items']

        logger.info(f"Loaded OneHotItemEncoder from {filepath}")
        logger.info(f"  {encoder.n_items_} items")

        return encoder
