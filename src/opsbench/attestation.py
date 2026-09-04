"""Cryptographic result attestations for tamper-evident OpsBench evaluations."""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime
import hashlib
import hmac
import json
from pathlib import Path
from typing import Any

from opsbench.runs import ResultBundle, load_result_bundle

ATTESTATION_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class ResultAttestation:
    """Cryptographic attestation certifying the authenticity of a benchmark result bundle."""

    bundle_hash: str
    signer_identity: str
    timestamp_utc: str
    signature: str
    metadata: dict[str, str] = field(default_factory=dict)
    schema_version: str = ATTESTATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.bundle_hash, str) or len(self.bundle_hash) != 64 or any(
            character not in "0123456789abcdef" for character in self.bundle_hash
        ):
            raise ValueError("bundle_hash must be a 64-character SHA-256 hex digest")
        if not isinstance(self.signer_identity, str) or not self.signer_identity.strip():
            raise ValueError("signer_identity must be a non-empty string")
        if not isinstance(self.timestamp_utc, str) or not self.timestamp_utc.strip():
            raise ValueError("timestamp_utc must be a non-empty ISO-8601 string")
        if not isinstance(self.signature, str) or not self.signature.strip():
            raise ValueError("signature must be a non-empty hex string")
        if self.schema_version != ATTESTATION_SCHEMA_VERSION:
            raise ValueError(f"unsupported attestation schema_version: {self.schema_version!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_hash": self.bundle_hash,
            "metadata": dict(self.metadata),
            "schema_version": self.schema_version,
            "signature": self.signature,
            "signer_identity": self.signer_identity,
            "timestamp_utc": self.timestamp_utc,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResultAttestation:
        return cls(
            bundle_hash=str(data["bundle_hash"]),
            signer_identity=str(data["signer_identity"]),
            timestamp_utc=str(data["timestamp_utc"]),
            signature=str(data["signature"]),
            metadata={str(k): str(v) for k, v in data.get("metadata", {}).items()},
            schema_version=str(data.get("schema_version", ATTESTATION_SCHEMA_VERSION)),
        )


def _canonical_payload(bundle_hash: str, signer_identity: str, timestamp_utc: str) -> bytes:
    """Create a canonical byte payload for signing."""
    msg = f"{bundle_hash}|{signer_identity}|{timestamp_utc}"
    return msg.encode("utf-8")


def sign_result_bundle(
    bundle_or_path: ResultBundle | Path | str,
    key: bytes | str,
    signer_identity: str,
    *,
    metadata: dict[str, str] | None = None,
    timestamp_utc: str | None = None,
) -> ResultAttestation:
    """Generate a signed cryptographic attestation for a benchmark result bundle."""
    if isinstance(bundle_or_path, (Path, str)):
        bundle = load_result_bundle(Path(bundle_or_path))
    elif isinstance(bundle_or_path, ResultBundle):
        bundle = bundle_or_path
    else:
        raise ValueError("bundle_or_path must be a ResultBundle or a Path")

    bundle_hash = bundle.content_hash()
    raw_key = key.encode("utf-8") if isinstance(key, str) else key
    if not isinstance(raw_key, bytes) or not raw_key:
        raise ValueError("signing key must be non-empty string or bytes")

    effective_timestamp = (
        timestamp_utc
        if timestamp_utc is not None
        else datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    payload = _canonical_payload(bundle_hash, signer_identity, effective_timestamp)
    signature = hmac.new(raw_key, payload, hashlib.sha256).hexdigest()

    return ResultAttestation(
        bundle_hash=bundle_hash,
        signer_identity=signer_identity,
        timestamp_utc=effective_timestamp,
        signature=signature,
        metadata=dict(metadata or {}),
    )


def verify_result_attestation(
    bundle_or_path: ResultBundle | Path | str,
    attestation: ResultAttestation,
    key: bytes | str,
) -> bool:
    """Verify that an attestation matches a result bundle and possesses a valid signature."""
    if isinstance(bundle_or_path, (Path, str)):
        bundle = load_result_bundle(Path(bundle_or_path))
    elif isinstance(bundle_or_path, ResultBundle):
        bundle = bundle_or_path
    else:
        raise ValueError("bundle_or_path must be a ResultBundle or a Path")

    if not isinstance(attestation, ResultAttestation):
        raise ValueError("attestation must be a ResultAttestation")

    raw_key = key.encode("utf-8") if isinstance(key, str) else key
    if not isinstance(raw_key, bytes) or not raw_key:
        raise ValueError("key must be non-empty string or bytes")

    # 1. Verify bundle content hash matches attestation
    bundle_hash = bundle.content_hash()
    if bundle_hash != attestation.bundle_hash:
        return False

    # 2. Verify signature
    payload = _canonical_payload(bundle_hash, attestation.signer_identity, attestation.timestamp_utc)
    expected_sig = hmac.new(raw_key, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_sig, attestation.signature)


def load_attestation(path: Path | str) -> ResultAttestation:
    """Load an attestation from a JSON file."""
    p = Path(path)
    if not p.is_file():
        raise ValueError(f"attestation file not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("attestation root must be a JSON object")
    return ResultAttestation.from_dict(data)


def write_attestation(path: Path | str, attestation: ResultAttestation) -> None:
    """Write an attestation to a JSON file."""
    if not isinstance(attestation, ResultAttestation):
        raise ValueError("attestation must be a ResultAttestation")
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(attestation.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
