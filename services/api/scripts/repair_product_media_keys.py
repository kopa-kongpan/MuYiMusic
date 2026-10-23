"""Repair legacy seed media references without relaxing store ownership checks."""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from botocore.exceptions import ClientError
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.models.product import Product, ProductImage
from app.providers.object_storage import ObjectStorageProvider


def target_key(prefix: str, key: str) -> str | None:
    if not key.startswith("seed/"):
        return None
    if any(part in {"", ".", ".."} for part in key.split("/")):
        raise ValueError(f"Invalid legacy media key: {key}")
    return prefix + key


def write_backup(backup: Path, report: dict[str, Any]) -> None:
    backup.parent.mkdir(parents=True, exist_ok=True)
    with backup.open("x", encoding="utf-8") as handle:
        backup.chmod(0o600)
        json.dump(report, handle, ensure_ascii=False, indent=2)


async def repair(
    *, apply: bool, backup: Path | None, allow_missing: bool, endpoint: str | None
) -> dict[str, Any]:
    settings = get_settings()
    if endpoint:
        settings = settings.model_copy(update={"object_storage_endpoint": endpoint})
    storage = ObjectStorageProvider(settings)
    async with get_session_factory()() as session:
        products = list(
            (await session.scalars(select(Product).with_for_update())).unique().all()
        )
        images = list((await session.scalars(select(ProductImage))).all())
        by_id = {product.id: product for product in products}
        changes: list[dict[str, str]] = []
        targets: list[tuple[Product | ProductImage, str, str]] = []
        for product in products:
            new_key = target_key(
                storage.expected_product_prefix(product.store_id),
                product.cover_object_key,
            )
            if new_key:
                changes.append(
                    {
                        "table": "products",
                        "id": str(product.id),
                        "old_key": product.cover_object_key,
                        "new_key": new_key,
                    }
                )
                targets.append((product, "cover_object_key", new_key))
        for image in images:
            product = by_id[image.product_id]
            new_key = target_key(
                storage.expected_product_prefix(product.store_id), image.object_key
            )
            if new_key:
                changes.append(
                    {
                        "table": "product_images",
                        "id": str(image.id),
                        "old_key": image.object_key,
                        "new_key": new_key,
                    }
                )
                targets.append((image, "object_key", new_key))
        report: dict[str, Any] = {"apply": apply, "changes": changes, "missing": []}
        if not apply:
            return report
        if backup is None:
            raise ValueError("--apply requires --backup")
        await asyncio.to_thread(write_backup, backup, report)
        if not changes:
            return report
        client: Any = storage._configured_client()
        bucket = settings.object_storage_bucket
        copied: set[tuple[str, str]] = set()
        for change in changes:
            pair = (change["old_key"], change["new_key"])
            if pair in copied:
                continue
            copied.add(pair)
            try:
                client.head_object(Bucket=bucket, Key=change["old_key"])
            except ClientError as error:
                if error.response["Error"]["Code"] not in {
                    "404",
                    "NoSuchKey",
                    "NotFound",
                }:
                    raise
                report["missing"].append(change["old_key"])
                if not allow_missing:
                    raise ValueError(
                        "Seed images are missing; upload them or use --allow-missing"
                    ) from error
                continue
            try:
                client.head_object(Bucket=bucket, Key=change["new_key"])
            except ClientError as error:
                if error.response["Error"]["Code"] not in {
                    "404",
                    "NoSuchKey",
                    "NotFound",
                }:
                    raise
                client.copy_object(
                    Bucket=bucket,
                    Key=change["new_key"],
                    CopySource={"Bucket": bucket, "Key": change["old_key"]},
                )
        for record, field, value in targets:
            setattr(record, field, value)
        await session.commit()
        return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--allow-missing", action="store_true")
    parser.add_argument("--storage-endpoint")
    args = parser.parse_args()
    report = asyncio.run(
        repair(
            apply=args.apply,
            backup=args.backup,
            allow_missing=args.allow_missing,
            endpoint=args.storage_endpoint,
        )
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
