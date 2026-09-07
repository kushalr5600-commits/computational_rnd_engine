from __future__ import annotations

import hashlib
import json
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

#: Version of the Design schema. Every generated architecture carries this so
#: consumers can reject/translate designs produced by older generators.
ARCHITECTURE_SCHEMA_VERSION: int = 1


class Domain(str, Enum):
    CPU = "cpu"
    GPU = "gpu"
    HETEROGENEOUS = "heterogeneous"

class Representation(BaseModel):
    isa_width: int = Field(64, ge=16, le=256)
    vector_width: int = Field(256, ge=32, le=4096)
    pipeline_depth: int = Field(12, ge=2, le=64)
    issue_width: int = Field(4, ge=1, le=32)
    execution_units: int = Field(8, ge=1, le=128)
    register_count: int = Field(64, ge=8, le=2048)

class Structure(BaseModel):
    l1_kb: int = Field(64, ge=4, le=4096)
    l2_kb: int = Field(1024, ge=64, le=65536)
    l3_kb: int = Field(16384, ge=0, le=524288)
    cache_line_bytes: int = Field(64, ge=16, le=256)
    memory_channels: int = Field(2, ge=1, le=64)
    interconnect_width: int = Field(256, ge=32, le=4096)

class Interactions(BaseModel):
    prefetch_strength: float = Field(0.5, ge=0, le=1)
    branch_predictor: float = Field(0.6, ge=0, le=1)
    data_reuse: float = Field(0.5, ge=0, le=1)
    parallelism: float = Field(0.5, ge=0, le=1)
    fusion: float = Field(0.3, ge=0, le=1)

class Transformation(BaseModel):
    loop_tiling: int = Field(32, ge=1, le=1024)
    unroll_factor: int = Field(4, ge=1, le=64)
    kernel_fusion: float = Field(0.3, ge=0, le=1)
    vectorization: float = Field(0.7, ge=0, le=1)

class SynthesizedComputation(BaseModel):
    parallel_lanes: int = Field(32, ge=1, le=4096)
    tensor_units: int = Field(0, ge=0, le=1024)
    specialized_units: int = Field(1, ge=0, le=512)
    clock_ghz: float = Field(2.5, ge=0.1, le=10.0)

class HardwareStrategy(BaseModel):
    technology_nm: int = Field(14, ge=3, le=180)
    voltage: float = Field(0.9, ge=0.3, le=1.8)
    frequency_scaling: float = Field(1.0, ge=0.2, le=4.0)
    parallel_blocks: int = Field(8, ge=1, le=1024)
    target: str = "generic"

class Primitive(BaseModel):
    name: str
    kind: str
    parameters: dict[str, Any] = Field(default_factory=dict)

class Design(BaseModel):
    id: str
    domain: Domain
    representation: Representation
    structure: Structure
    interactions: Interactions
    transformations: list[Transformation]
    synthesized: SynthesizedComputation
    hardware: HardwareStrategy
    primitives: list[Primitive] = Field(default_factory=list)
    parent_ids: list[str] = Field(default_factory=list)
    generation: int = 0
    architecture_schema_version: int = Field(ARCHITECTURE_SCHEMA_VERSION, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)


def design_id(design: Design) -> str:
    """Deterministic content-addressed UUID-format identifier for a Design.

    The digest is computed over the design's stable serialized contents with its
    own ``id`` field excluded, avoiding a circular self-reference when the ID is
    stored on the very object it describes. ``parent_ids`` participate in the
    digest so evolved children keep deterministic parent/child relationships and
    designs with distinct ancestry cannot collide. Keys are normalized with
    ``sort_keys`` so identical designs produce identical IDs across processes.
    ``architecture_schema_version`` and ``provenance`` participate in the digest
    so a design's identity is bound to the generator configuration that produced
    it.
    """
    payload = design.model_dump(mode="json")
    payload.pop("id", None)
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(blob).hexdigest()[:32]
    return str(uuid.UUID(hex=digest))


class BenchmarkResult(BaseModel):
    workload: str
    runtime_s: float
    memory_mb: float
    energy_j: float
    correct: bool
    samples: int
    variance: float
    evidence_level: str = "surrogate"

class Metrics(BaseModel):
    baseline_cost: float
    optimized_cost: float
    correctness_error: float
    generalization: float
    utility: float
    novelty: float
    reusability: float
    hardware_efficiency: float
    useful_structure: float
    search_cost: float
    memory_cost: float
    complexity_cost: float
    energy_cost: float
    fragility: float
    future_discovery_rate: float
    search_efficiency: float
    reproducibility: float
    evidence: dict[str, Any] = Field(default_factory=dict)
    benchmark_results: list[BenchmarkResult] = Field(default_factory=list)

class OmegaScore(BaseModel):
    omega: float
    amplification: float
    numerator: float
    denominator: float
    metrics: Metrics
    verified: bool
    constraints_satisfied: bool

class Candidate(BaseModel):
    design: Design
    metrics: Metrics | None = None
    score: OmegaScore | None = None
    status: str = "generated"

class ResearchRecord(BaseModel):
    candidate_id: str
    generation: int
    status: str
    omega: float
    amplification: float
    llm_calls: int = 0
    provenance: dict[str, Any] = Field(default_factory=dict)
