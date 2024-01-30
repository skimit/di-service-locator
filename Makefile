.PHONY: help clean list-containers start-dependencies stop-dependencies run enter-container show-container-logs test coverage sync-requirements

PROJECT_NAME=di-service-locator

###############################################################################################
# ⚠️ Please, don't change anything bellow this message, unless you know what you're doing! ⚠️  #
###############################################################################################

PROJECT_INSTANCES := $(shell docker ps | awk -v count=0 '/${PROJECT_NAME}/ {count++} END {print count}')
PROJECT_CONTAINERS := $(shell docker ps | awk '/${PROJECT_NAME}/ {print $$(NF)}')
PROJECT_MAIN_DOCKER_IMAGE := $(shell docker images | awk '/${PROJECT_NAME}/ {print $$1}')
ENV_FILE := $(shell test -e .env && echo 0 || echo -1)
POETRY_LOCK_HASH := $(shell command -v sha1sum >/dev/null && echo $$(sha1sum pyproject.toml) | cut -d ' ' -f 1 || echo -1)

FILES_CHANGED := $(strip $(foreach file, $(FILES_TO_CHECK_FOR_CHANGES), $(shell \
                    if [ $$(git diff --name-only HEAD~1 HEAD | grep ${file} | wc -l | xargs) = '1' ]; then \
                        echo "--build"; \
                    fi; \
                )))
REBUILD_FLAG := $(shell echo "$(FILES_CHANGED)" | cut -d " " -f1)

define ANNOUNCEMENT
	@echo
	@echo " \033[92m*** $1 ***\033[0m"
	@echo
endef

define DOCKER_EXEC
	@docker exec -it $1 bash -c $2
endef

define DOCKER_LOGS
	@docker logs -f $1
endef

help:	# The following lines will print the available commands when entering just 'make', as long as a comment with three cardinals is found after the recipe name. Look at the examples below.
ifeq ($(UNAME), Linux)
	@grep -P '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
else
	@awk -F ':.*###' '$$0 ~ FS {printf "%15s%s\n", $$1 ":", $$2}' \
		$(MAKEFILE_LIST) | grep -v '@awk' | sort
endif

clean:	### Removes cache, compiled files, coverage results and other files.
	find . -name '__pycache__' -exec rm -rf {} +
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '.coverage' -exec rm -f {} +
	find . -name '.coverage.xml' -exec rm -f {} +
	find . -name 'htmlcov' -exec rm -rf {} +
	find . -name '.pytest_cache' -exec rm -rf {} +
	rm -rf di_features/.egg-info/ build/ dist/ .cache/

list-containers:	### Lists all of the project-related running containers
	$(call ANNOUNCEMENT,Available $(PROJECT_NAME) containers)
	@echo $(foreach container, $(PROJECT_CONTAINERS), "\t • ${container}"; echo "")


start-dependencies:	### Starts all of the project-related containers, on background
ifeq ($(strip $(ENV_FILE)),-1)
	$(call ANNOUNCEMENT,Could not find .env file. Please make sure that it exists!)
else
ifneq ($(strip $(PROJECT_INSTANCES)),0)
	$(call ANNOUNCEMENT,Dependencies are up and running. Nothing to do here...)
else
ifdef REBUILD_FLAG
	$(call ANNOUNCEMENT,Rebuilding docker image!)
endif
	$(call ANNOUNCEMENT,Starting dependencies...)
	@PROJECT_NAME=$(PROJECT_NAME) PORT=$(PORT) POETRY_LOCK_HASH=$(POETRY_LOCK_HASH) docker compose -p $(PROJECT_NAME) -f docker/docker-compose.yml up -d $(REBUILD_FLAG)
endif
endif


stop-dependencies:	### Stops all of the project-related containers
ifneq ($(strip $(PROJECT_INSTANCES)),0)
	@PROJECT_NAME=$(PROJECT_NAME) PORT=$(PORT) docker compose -p $(PROJECT_NAME) -f docker/docker-compose.yml down
else
	$(call ANNOUNCEMENT,Dependencies are not up and running. Nothing to do here...)
endif

run:	### Executes project's main.py on the running container
ifeq ($(strip $(PROJECT_INSTANCES)),0)
	$(call ANNOUNCEMENT,Error executing $(PROJECT_NAME). Are the dependencies up and running?)
else
	$(call ANNOUNCEMENT,Starting $(PROJECT_NAME)...)
	$(call DOCKER_EXEC,$(PROJECT_NAME),"reflex -d none -s -r '(\.py$$)' -- bash -c 'python $(PROJECT_NAME)/main.py'")
endif

enter-container:	### Gives shell access to the specified project-related container
ifeq ($(strip $(PROJECT_INSTANCES)),0)
	$(call ANNOUNCEMENT,Error entering $(PROJECT_NAME) container. Are the dependencies up and running?)
else
ifndef CONTAINER
	$(call ANNOUNCEMENT,Error entering container: missing container name. Usage: make enter-container CONTAINER=name_of_your_container)
else
ifeq ($(filter $(CONTAINER),$(PROJECT_CONTAINERS)),)
	$(call ANNOUNCEMENT,Error entering container: invalid container name provided. Execute 'make list-containers' to retrieve the valid list)
else
	$(call DOCKER_EXEC,$(CONTAINER),"bash")
endif
endif
endif

show-container-logs:	### Continuously shows the given container name logs output
ifeq ($(strip $(PROJECT_INSTANCES)),0)
	$(call ANNOUNCEMENT,Error showing $(PROJECT_NAME) logs. Are the dependencies up and running?)
else
ifndef CONTAINER
	$(call ANNOUNCEMENT,Error entering container: missing container name. Usage: make enter-container CONTAINER=name_of_your_container)
else
ifeq ($(filter $(CONTAINER),$(PROJECT_CONTAINERS)),)
	$(call ANNOUNCEMENT,Error entering container: invalid container name provided. Execute 'make list-containers' to retrieve the valid list)
else
	$(call DOCKER_LOGS,$(CONTAINER))
endif
endif
endif

test:	### Runs the project tests'
ifeq ($(strip $(PROJECT_INSTANCES)),0)
	$(call ANNOUNCEMENT,Error running $(PROJECT_NAME) tests. Are the dependencies up and running?)
else
	$(call ANNOUNCEMENT,Preparing testing environment)
	$(call DOCKER_EXEC,$(PROJECT_NAME),"poetry run task test $(EXTRA_ARGUMENTS)")
endif

coverage:	### Runs the project tests' and generates the coverage report
ifeq ($(strip $(PROJECT_INSTANCES)),0)
	$(call ANNOUNCEMENT,Error executing $(PROJECT_NAME) coverage report. Are the dependencies up and running?)
else
	$(call ANNOUNCEMENT,Preparing testing environment)
	$(call DOCKER_EXEC,$(PROJECT_NAME),"poetry run task coverage")
	$(call DOCKER_EXEC,$(PROJECT_NAME),"coverage report -m")
endif

sync-requirements:	### Syncs the installed dependencies with the ones defined on requirements.txt. This will delete project's main Docker image and rebuild it again
ifeq ($(strip $(PROJECT_INSTANCES)),0)
	$(call ANNOUNCEMENT,Syncing project requirements...)
	@docker image rm $(PROJECT_MAIN_DOCKER_IMAGE)
	@PROJECT_NAME=$(PROJECT_NAME) PORT=$(PORT) POETRY_LOCK_HASH=$(POETRY_LOCK_HASH) docker compose -p $(PROJECT_NAME) -f docker/docker-compose.yml build
else
	$(call ANNOUNCEMENT,Error syncing $(PROJECT_NAME) requirements. Please stop all running dependencies and try again.)
endif
