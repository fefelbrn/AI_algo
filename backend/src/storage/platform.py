"""Storage platform facade — single entry point for Step 4."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.paths import backend_root
from src.storage.config import StorageConfig, load_storage_config
from src.storage.layers import DataLayer
from src.storage.metadata import MetadataStore
from src.storage.parquet_io import ParquetLayerWriter
from src.storage.partitions import PartitionPathBuilder, PartitionRef
from src.storage.schemas import LAYER_SCHEMAS, PLATFORM_SCHEMA_VERSION


@dataclass
class StoragePlatform:
    artifacts_dir: Path
    config: StorageConfig
    metadata: MetadataStore
    partitions: PartitionPathBuilder
    parquet: ParquetLayerWriter

    @classmethod
    def open(cls, artifacts_dir: Path, config_dir: Path | None = None) -> "StoragePlatform":
        cfg = load_storage_config(config_dir or backend_root() / "configs")
        db_path = artifacts_dir / cfg.metadata.db_subdir / cfg.metadata.db_filename
        platform = cls(
            artifacts_dir=artifacts_dir,
            config=cfg,
            metadata=MetadataStore(db_path),
            partitions=PartitionPathBuilder(artifacts_dir, cfg),
            parquet=ParquetLayerWriter(cfg),
        )
        platform.bootstrap_schemas()
        return platform

    def bootstrap_schemas(self) -> None:
        from src.collectors.models import iso_ts

        ts = iso_ts()
        for layer, schema in LAYER_SCHEMAS.items():
            self.metadata.register_schema(
                layer.value,
                PLATFORM_SCHEMA_VERSION,
                len(schema.names),
                ts,
            )

    def write_parquet_partition(
        self,
        layer: DataLayer,
        rows: list[dict[str, Any]],
        *,
        trade_date: str,
        filename: str,
        run_id: str,
        session_id: str | None = None,
        underlying: str | None = None,
        product: str | None = None,
        source_layers: list[tuple[str, str]] | None = None,
        version_id: str | None = None,
    ) -> tuple[Path, PartitionRef]:
        from src.collectors.models import iso_ts

        directory = self.partitions.layer_dir(
            layer,
            trade_date,
            session_id=session_id,
            underlying=underlying,
            product=product,
        )
        path = directory / filename
        count = self.parquet.write_rows(layer, rows, path)
        ref = self.partitions.partition_ref(
            layer,
            trade_date,
            directory,
            session_id=session_id,
            underlying=underlying,
            product=product,
        )
        vid = version_id or f"{PLATFORM_SCHEMA_VERSION}_{run_id}"
        self.metadata.register_partition(
            layer=layer.value,
            trade_date=trade_date,
            partition_key=ref.partition_key,
            partition_path=str(path),
            record_count=count,
            schema_version=PLATFORM_SCHEMA_VERSION,
            version_id=vid,
            source_run_id=run_id,
            created_at=iso_ts(),
            source_layers=source_layers,
        )
        return path, ref

    def write_manifest(self, directory: Path, manifest: dict[str, Any]) -> Path:
        path = directory / "session_manifest.json"
        path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
        return path

    def read_layer_partition(self, path: Path, layer: DataLayer):
        return self.parquet.read_partition(path, layer=layer)
