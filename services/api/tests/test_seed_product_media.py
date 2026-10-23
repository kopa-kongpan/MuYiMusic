import runpy
from pathlib import Path
from uuid import UUID

import pytest

from app.core.config import Settings
from app.providers.object_storage import ObjectStorageProvider
from scripts.repair_product_media_keys import target_key


def test_seed_product_media_obeys_store_ownership_validation() -> None:
    generator = runpy.run_path(
        str(Path(__file__).resolve().parents[3] / "deploy/seed/generate_seed_sql.py")
    )
    sql = generator["build"]()
    product_sql = sql.split("INSERT INTO products", 1)[1].split(
        "INSERT INTO teachers", 1
    )[0]
    assert "'seed/" not in product_sql
    storage = ObjectStorageProvider(Settings(_env_file=None))
    for store_key, _category, _name, _summary, cover, _sales, _skus in generator[
        "PRODUCTS"
    ]:
        store_id = UUID(generator["uid"](f"store:{store_key}"))
        other_store = "store-b" if store_key == "store-a" else "store-a"
        other_id = UUID(generator["uid"](f"store:{other_store}"))
        key = generator["product_media_key"](store_key, cover)
        assert key in product_sql
        assert storage.is_product_object_key(store_id, key)
        assert not storage.is_product_object_key(other_id, key)


@pytest.mark.parametrize(
    "key",
    [
        "",
        "https://example.com/seed/cover.png",
        "other-store/cover.png",
        "muyimusic/stores/other-store/products/cover.png",
    ],
)
def test_repair_does_not_reassign_non_seed_media(key: str) -> None:
    assert target_key("muyimusic/stores/current-store/products/", key) is None


@pytest.mark.parametrize("key", ["seed/../cover.png", "seed//cover.png", "seed/."])
def test_repair_rejects_ambiguous_seed_paths(key: str) -> None:
    with pytest.raises(ValueError, match="Invalid legacy media key"):
        target_key("muyimusic/stores/current-store/products/", key)
