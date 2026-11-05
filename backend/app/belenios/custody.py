"""Approved external trustee counts, kept outside native cryptographic payloads."""
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class TrusteePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    count: int = Field(strict=True, ge=3, le=9)
    threshold: int = Field(strict=True, ge=2)

    @model_validator(mode="after")
    def supported_threshold(self):
        # The pinned native Threshold API requires threshold < number of trustees.
        if self.threshold >= self.count:
            raise ValueError("El umbral debe ser menor que el número de custodios.")
        return self


def approved_policy(binding):
    try:
        return TrusteePolicy.model_validate_json(binding.trustee_policy_json).model_dump()
    except (ValidationError, TypeError):
        raise HTTPException(409, "Falta una política de custodios aprobada y registrada para esta vinculación; no se inferirá del proveedor.") from None


def ceremony_matches(trustees, policy):
    if not isinstance(trustees, list) or len(trustees) != 2 or trustees[0] != "Threshold":
        return False
    details = trustees[1]
    return (isinstance(details, dict) and type(details.get("threshold")) is int
            and details["threshold"] == policy["threshold"]
            and isinstance(details.get("trustees"), list)
            and len(details["trustees"]) == policy["count"])
