# computational-rnd-engine — EDA environment management
#
# Targets:
#   make build    — build the EDA container image
#   make doctor   — run rnd-engine eda-doctor inside the container
#   make flow     — run a full hardware flow on the best surrogate candidate
#   make lint     — run lint stage only
#   make simulate — run simulation stage only
#   make synth    — run synthesis stage only
#   make physical — run physical stage only
#   make signoff  — run signoff (full flow)
#   make shell    — open an interactive shell in the container
#
# Environment variables:
#   PDK_ROOT — path to the mounted PDK tree (read-only)
#   PROFILE  — PDK profile (default: sky130)
#   POPULATION / GENERATIONS / SEED — search parameters

PROFILE ?= sky130
POPULATION ?= 8
GENERATIONS ?= 1
SEED ?= 42
IMAGE ?= rnd-engine-eda:stable
PDK_ROOT ?= /nonexistent
DOCKER_RUN = docker run --rm -i \
	--memory=6g --cpus=3 \
-v $(CURDIR):/work \
-v $(PDK_ROOT):/pdk:ro \
-e PDK_ROOT=/pdk \
-e RND_ENGINE_CONFIG_DIR=/work/configs

.PHONY: build doctor flow lint simulate synth physical signoff shell

build:
	docker build -t $(IMAGE) eda/

doctor:
	$(DOCKER_RUN) $(IMAGE) rnd-engine eda-doctor --profile $(PROFILE)

flow:
	$(DOCKER_RUN) $(IMAGE) rnd-engine flow --profile $(PROFILE) \
	--population $(POPULATION) --generations $(GENERATIONS) --seed $(SEED)

lint:
	$(DOCKER_RUN) $(IMAGE) rnd-engine flow --stages lint --profile $(PROFILE) \
	--population $(POPULATION) --generations $(GENERATIONS) --seed $(SEED)

signoff:
	$(DOCKER_RUN) $(IMAGE) rnd-engine signoff --profile $(PROFILE) \
	--population $(POPULATION) --generations $(GENERATIONS) --seed $(SEED)

shell:
	$(DOCKER_RUN) --entrypoint /bin/bash $(IMAGE)