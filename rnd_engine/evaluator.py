from __future__ import annotations

import hashlib
import math
import random
import statistics

from .models import BenchmarkResult, Design, Metrics


class Evaluator:
    """Deterministic reference evaluator. Replace via adapters for gem5/RTL/P&R."""
    def __init__(self, workloads: list[str] | None = None):
        self.workloads = workloads or ["matmul", "stencil", "reduction", "branchy", "memory_stream"]

    def evaluate(self, design: Design, archive: list[Design]) -> Metrics:
        seed = int(hashlib.sha256(design.model_dump_json().encode()).hexdigest()[:16], 16)
        rng = random.Random(seed)
        p, s, i, t, c, h = (design.representation, design.structure, design.interactions,
                            design.transformations[0], design.synthesized, design.hardware)
        compute = 0.10*math.log2(p.issue_width+1) + 0.08*math.log2(p.execution_units+1) \
                + 0.08*math.log2(p.vector_width/64) + 0.10*math.log2(c.parallel_lanes+1)
        memory = 0.08*math.log2(s.l1_kb/4) + 0.07*math.log2(s.l2_kb/64) \
               + 0.05*math.log2(max(1,s.l3_kb)/1024) + 0.10*i.data_reuse + 0.07*i.prefetch_strength
        transform = 0.08*math.log2(t.unroll_factor) + 0.07*math.log2(t.loop_tiling) \
                  + 0.10*t.vectorization + 0.08*t.kernel_fusion
        tech = max(0.0, min(1.0, (28-h.technology_nm)/25))
        complexity = 0.03*p.pipeline_depth + 0.04*p.issue_width + 0.01*p.execution_units \
                   + 0.0005*s.l3_kb + 0.02*c.specialized_units
        quality_factor = 1.0 + compute + memory + transform + 0.12*tech
        baseline = 100.0
        optimized = baseline / max(quality_factor + 0.02*rng.random(), 0.1)
        correctness_error = 0.0 if p.pipeline_depth <= 60 and s.cache_line_bytes in {32,64,128} else 1e-2
        generalization = min(1.0, 0.55 + 0.25*i.parallelism + 0.10*i.data_reuse + 0.10*(1-i.fusion*0.5))
        novelty = self._novelty(design, archive)
        reusability = min(1.0, 0.65 + 0.20*i.data_reuse + 0.10*i.parallelism + 0.05*t.vectorization)
        utility = min(1.0, 0.35*min(1, compute+0.5) + 0.35*min(1, memory+0.5) + 0.30*min(1, transform+0.5))
        hw_eff = min(1.0, max(0.0, 0.55 + 0.25*tech + 0.10*h.frequency_scaling - 0.03*max(0, complexity-2)))
        useful_structure = min(1.0, 0.25*i.data_reuse + 0.25*i.parallelism + 0.25*i.prefetch_strength + 0.25*t.vectorization)
        search_cost = 0.01 + 0.002*len(design.primitives)
        memory_cost = min(10_000, s.l3_kb/8192 + s.l2_kb/8192)
        energy_cost = max(0.01, 0.25*h.voltage*h.voltage*h.frequency_scaling + 0.015*p.execution_units + 0.01*c.specialized_units)
        fragility = min(1.0, 0.02*max(0,p.pipeline_depth-24) + 0.04*max(0,p.issue_width-8) + 0.02*max(0,c.specialized_units-32))
        future = min(1.0, 0.45 + 0.25*novelty + 0.20*useful_structure + 0.10*reusability)
        search_eff = max(0.0, min(1.0, 0.75 - search_cost + 0.20*novelty))
        benches = self._benchmark_summary(design, optimized, correctness_error, rng)
        variance = statistics.pvariance([b.runtime_s for b in benches]) if len(benches) > 1 else 0.0
        return Metrics(
            baseline_cost=baseline, optimized_cost=optimized,
            correctness_error=correctness_error, generalization=generalization,
            utility=utility, novelty=novelty, reusability=reusability,
            hardware_efficiency=hw_eff, useful_structure=useful_structure,
            search_cost=search_cost, memory_cost=memory_cost,
            complexity_cost=max(0.0,complexity), energy_cost=energy_cost,
            fragility=min(1.0, fragility+variance), future_discovery_rate=future,
            search_efficiency=search_eff, reproducibility=max(0.0, min(1.0, 0.99-variance)),
            evidence={"type":"deterministic_surrogate", "authoritative":False},
            benchmark_results=benches,
        )

    def _benchmark_summary(self, d: Design, optimized: float, error: float, rng: random.Random) -> list[BenchmarkResult]:
        out=[]
        weights={"matmul":1.0,"stencil":1.1,"reduction":0.9,"branchy":1.2,"memory_stream":1.25}
        for w in self.workloads:
            noise=0.005+0.01*rng.random()
            runtime=max(1e-6, optimized*weights.get(w,1.0)*0.001*(1+noise))
            mem=64.0 + d.structure.l2_kb*0.02 + d.structure.l3_kb*0.002
            power=20.0 + d.representation.execution_units*0.5 + d.hardware.voltage**2*d.synthesized.clock_ghz*10
            out.append(BenchmarkResult(workload=w, runtime_s=runtime, memory_mb=mem, energy_j=runtime*power,
                                       correct=(error==0), samples=5, variance=noise**2, evidence_level="surrogate"))
        return out

    def _novelty(self, design: Design, archive: list[Design]) -> float:
        if not archive: return 1.0
        v=self._vector(design)
        def dist(a):
            av=self._vector(a); return (sum((x-y)**2 for x,y in zip(v,av))/len(v))**0.5
        d=sum(dist(a) for a in archive[-200:])/min(len(archive),200)
        return min(1.0, d*3.0)

    def _vector(self,d:Design):
        p,s,i,t,c,h=(d.representation,d.structure,d.interactions,d.transformations[0],d.synthesized,d.hardware)
        return [p.pipeline_depth/64,p.issue_width/32,p.execution_units/128,p.vector_width/4096,
                s.l1_kb/4096,s.l2_kb/65536,s.l3_kb/524288,i.data_reuse,i.parallelism,t.unroll_factor/64,
                t.vectorization,c.parallel_lanes/4096,c.specialized_units/512,h.technology_nm/180,h.voltage/1.8]
