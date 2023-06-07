help:
	@echo "This is the help for the Makefile"
	@echo "----------------------------------------"
	@echo "install      : installs required Python packages"
	@echo "run          : runs the application locally"
	@echo "dcompose     : runs docker-compose after cleaning up the image"
	@echo "docker-build : builds the docker image"
	@echo "docker-run   : runs the docker image"
	@echo "docker-stop  : stops the docker image"
	@echo "docker-remove: removes the docker image"
	@echo "docker-clean : cleans the docker image"
	@echo "docker-restart: restarts the docker image"
	@echo "docker-rebuild: rebuilds the docker image"
	@echo "docker-logs  : shows the docker logs"
	@echo "docker-shell : opens a shell in the docker image"

install:
	@cp .env.default .env
	@source .env
	@pip install -r requirements.txt
	
run:
	@python main.py

dcompose:
	@docker-compose -f docker/docker-compose.yaml down
	@docker rmi -f docker-aleph-tezos-event-indexer
	@docker-compose -f docker/docker-compose.yaml up -d

docker-build:
	@docker build . -f ./docker/Dockerfile -t aleph-tezos-event-indexer

docker-run:
	@docker run --name aleph-tezos-event-indexer aleph-tezos-event-indexer

docker-stop:
	@docker stop aleph-tezos-event-indexer

docker-remove:
	@docker rm aleph-tezos-event-indexer

docker-clean:
	@docker rmi aleph-tezos-event-indexer

docker-restart: docker-stop docker-remove docker-build docker-run

docker-rebuild: docker-stop docker-remove docker-clean docker-build docker-run

docker-logs:
	@docker logs -f aleph-tezos-event-indexer

docker-shell:
	@docker exec -it aleph-tezos-event-indexer /bin/bash