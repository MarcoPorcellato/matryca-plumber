from __future__ import annotations

import json

from pydantic import BaseModel

from .models import DocumentV1, EvidenceV1, PackManifestV1

_SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "schemas/document.schema.json": DocumentV1,
    "schemas/evidence.schema.json": EvidenceV1,
    "schemas/pack-manifest.schema.json": PackManifestV1,
}


def _schema_artifact_bytes(schema: object) -> bytes:
    return json.dumps(
        schema,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def render_schema_files() -> dict[str, bytes]:
    return {
        path: _schema_artifact_bytes(
            model.model_json_schema(
                mode="validation",
                ref_template="#/$defs/{model}",
            )
        )
        for path, model in sorted(_SCHEMA_MODELS.items())
    }
