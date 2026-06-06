"""Partition path conventions — dt / session_id / underlying / product."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.storage.config import PartitioningConfig, StorageConfig
from src.storage.layers import DataLayer


@dataclass(frozen=True)
class PartitionRef:
    layer: DataLayer
    trade_date: str
    path: Path
    session_id: str | None = None
    underlying: str | None = None
    product: str | None = None

    @property
    def partition_key(self) -> str:
        parts = [f"dt={self.trade_date}"]
        if self.underlying:
            parts.append(f"underlying={self.underlying}")
        if self.product:
            parts.append(f"product={self.product}")
        if self.session_id:
            parts.append(f"session_id={self.session_id}")
        return "/".join(parts)


class PartitionPathBuilder:
    def __init__(self, artifacts_dir: Path, config: StorageConfig) -> None:
        self._root = artifacts_dir
        self._keys = config.partitioning

    def layer_dir(
        self,
        layer: DataLayer,
        trade_date: str,
        *,
        session_id: str | None = None,
        underlying: str | None = None,
        product: str | None = None,
    ) -> Path:
        p = self._root / layer.value / f"{self._keys.date_key}={trade_date}"
        if underlying:
            p /= f"{self._keys.underlying_key}={underlying}"
        if product:
            p /= f"{self._keys.product_key}={product}"
        if session_id:
            p /= f"{self._keys.session_key}={session_id}"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def parquet_file(
        self,
        layer: DataLayer,
        trade_date: str,
        filename: str,
        *,
        session_id: str | None = None,
        underlying: str | None = None,
        product: str | None = None,
    ) -> Path:
        return self.layer_dir(
            layer,
            trade_date,
            session_id=session_id,
            underlying=underlying,
            product=product,
        ) / filename

    def partition_ref(
        self,
        layer: DataLayer,
        trade_date: str,
        directory: Path,
        *,
        session_id: str | None = None,
        underlying: str | None = None,
        product: str | None = None,
    ) -> PartitionRef:
        return PartitionRef(
            layer=layer,
            trade_date=trade_date,
            path=directory,
            session_id=session_id,
            underlying=underlying,
            product=product,
        )
