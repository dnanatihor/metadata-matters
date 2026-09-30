"""Pydantic models for the YAML files under ``configs/``.

Chat-model choice and a positive spend cap are left unset. SPEC.md §12.1 is
still an open decision; ``budget.max_usd: 0`` means no paid run is authorised.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Literal, TypeVar

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from mm.paths import repo_root

T = TypeVar("T", bound=BaseModel)


class ModelKind(StrEnum):
    """Whether a configured model is a chat model or an embedding model."""

    CHAT = "chat"
    EMBEDDING = "embedding"


class SampleConfig(BaseModel):
    """How many examples a run draws from the loaded dataset."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    n: int | Literal["all"] = 500
    seed: int = 0

    @field_validator("n")
    @classmethod
    def _positive_sample(cls, value: int | str) -> int | str:
        if isinstance(value, int) and value < 1:
            message = "sample.n must be an integer >= 1 or 'all'"
            raise ValueError(message)
        return value


class BudgetConfig(BaseModel):
    """Spend cap checked before a run starts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_usd: float

    @field_validator("max_usd")
    @classmethod
    def _non_negative(cls, value: float) -> float:
        if value < 0:
            message = "budget.max_usd must be >= 0"
            raise ValueError(message)
        return value


class RunConfig(BaseModel):
    """Shared fields of ``configs/rq*.yaml``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rq: Literal["rq1", "rq2", "rq3", "rq4"]
    sample: SampleConfig = Field(default_factory=SampleConfig)
    budget: BudgetConfig
    models: list[str] = Field(default_factory=list)


class ModelSpec(BaseModel):
    """One entry in ``configs/models.yaml``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    kind: ModelKind
    provider: str


class ModelsConfig(BaseModel):
    """Catalog of models a run may name."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    models: list[ModelSpec]


class TokenPrice(BaseModel):
    """Hand-maintained token price for one model. Check before a paid run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_id: str
    usd_per_million_input_tokens: float
    usd_per_million_output_tokens: float

    @field_validator("usd_per_million_input_tokens", "usd_per_million_output_tokens")
    @classmethod
    def _non_negative(cls, value: float) -> float:
        if value < 0:
            message = "token prices must be >= 0"
            raise ValueError(message)
        return value


class PricesConfig(BaseModel):
    """Contents of ``configs/prices.yaml``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    prices: list[TokenPrice]


def load_yaml_model(path: Path, model: type[T]) -> T:
    """Parse a YAML file into ``model``."""
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return model.model_validate(loaded)


def configs_dir() -> Path:
    return repo_root() / "configs"


def load_run_config(path: Path) -> RunConfig:
    return load_yaml_model(path, RunConfig)


def load_models_config(path: Path) -> ModelsConfig:
    return load_yaml_model(path, ModelsConfig)


def load_prices_config(path: Path) -> PricesConfig:
    return load_yaml_model(path, PricesConfig)
