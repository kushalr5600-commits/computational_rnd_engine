from __future__ import annotations

import copy
import random
from typing import Any

from .models import *
from .reproducibility import configuration_fingerprint


class SearchEngine:
    def __init__(self, seed=42, objective_config: dict[str, Any] | None = None):
        self.search_seed = seed
        self.rng = random.Random(seed)
        self.objective_config = objective_config

    def _provenance(self) -> dict[str, Any]:
        search_config = {
            "engine": type(self).__name__,
            "rng": type(self.rng).__name__,
            "seed": self.search_seed,
        }
        return {
            "seed": self.search_seed,
            "search_config": search_config,
            "objective_config": self.objective_config,
            "configuration_fingerprint": configuration_fingerprint(
                search_config,
                self.objective_config,
                ARCHITECTURE_SCHEMA_VERSION,
            ),
        }

    def seed(self,n,domain): return [self.random_design(domain,0) for _ in range(n)]
    def random_design(self,domain,g):
        design = Design(id="",domain=domain,generation=g,provenance=self._provenance(),
            representation=Representation(isa_width=self.rng.choice([32,64,128]),vector_width=self.rng.choice([128,256,512,1024,2048]),pipeline_depth=self.rng.randint(6,32),issue_width=self.rng.randint(1,12),execution_units=self.rng.randint(2,32),register_count=self.rng.choice([32,64,128,256])),
            structure=Structure(l1_kb=self.rng.choice([32,64,128,256,512]),l2_kb=self.rng.choice([256,512,1024,2048,4096,8192]),l3_kb=self.rng.choice([0,4096,8192,16384,32768,65536]),cache_line_bytes=self.rng.choice([32,64,128]),memory_channels=self.rng.randint(1,16),interconnect_width=self.rng.choice([64,128,256,512,1024])),
            interactions=Interactions(prefetch_strength=self.rng.random(),branch_predictor=self.rng.random(),data_reuse=self.rng.random(),parallelism=self.rng.random(),fusion=self.rng.random()),
            transformations=[Transformation(loop_tiling=self.rng.choice([8,16,32,64,128]),unroll_factor=self.rng.choice([1,2,4,8,16]),kernel_fusion=self.rng.random(),vectorization=self.rng.random())],
            synthesized=SynthesizedComputation(parallel_lanes=self.rng.choice([8,16,32,64,128,256,512]),tensor_units=self.rng.randint(0,64),specialized_units=self.rng.randint(0,32),clock_ghz=round(self.rng.uniform(1,4.5),2)),
            hardware=HardwareStrategy(technology_nm=self.rng.choice([180,90,45,28,16,14,7,5,3]),voltage=round(self.rng.uniform(.65,1.15),2),frequency_scaling=round(self.rng.uniform(.7,1.5),2),parallel_blocks=self.rng.choice([1,2,4,8,16,32,64]),target=domain.value))
        design.id = design_id(design)
        return design
    def evolve(self,parents,g,count):
        out=[]
        for _ in range(count):
            child=copy.deepcopy(self.rng.choice(parents)); pid=child.id; child.id=""; child.parent_ids=[pid]; child.generation=g
            self.mutate(child); child.id=design_id(child)
            out.append(child)
        return out
    def mutate(self,d):
        p,s,i,t,c,h=(d.representation,d.structure,d.interactions,d.transformations[0],d.synthesized,d.hardware)
        ops=[lambda:setattr(p,'issue_width',max(1,min(32,p.issue_width+self.rng.choice([-2,-1,1,2])))),lambda:setattr(p,'pipeline_depth',max(2,min(64,p.pipeline_depth+self.rng.choice([-2,-1,1,2])))),lambda:setattr(p,'execution_units',max(1,min(128,p.execution_units+self.rng.choice([-2,-1,1,2])))),lambda:setattr(p,'vector_width',self.rng.choice([64,128,256,512,1024,2048,4096])),lambda:setattr(s,'l1_kb',self.rng.choice([32,64,128,256,512,1024])),lambda:setattr(s,'l2_kb',self.rng.choice([256,512,1024,2048,4096,8192,16384])),lambda:setattr(s,'l3_kb',self.rng.choice([0,4096,8192,16384,32768,65536,131072])),lambda:setattr(i,'data_reuse',self._b(i.data_reuse+self.rng.uniform(-.15,.15))),lambda:setattr(i,'parallelism',self._b(i.parallelism+self.rng.uniform(-.15,.15))),lambda:setattr(i,'prefetch_strength',self._b(i.prefetch_strength+self.rng.uniform(-.15,.15))),lambda:setattr(t,'unroll_factor',self.rng.choice([1,2,4,8,16,32,64])),lambda:setattr(t,'vectorization',self._b(t.vectorization+self.rng.uniform(-.15,.15))),lambda:setattr(c,'parallel_lanes',self.rng.choice([8,16,32,64,128,256,512,1024])),lambda:setattr(c,'specialized_units',max(0,min(512,c.specialized_units+self.rng.choice([-4,-2,2,4])))),lambda:setattr(h,'technology_nm',self.rng.choice([180,90,45,28,16,14,7,5,3])),lambda:setattr(h,'voltage',round(max(.3,min(1.8,h.voltage+self.rng.uniform(-.05,.05))),2))]
        for _ in range(self.rng.randint(1,4)): self.rng.choice(ops)()
    def _b(self,x): return max(0,min(1,x))
