help:
	@echo "This is the help for the Makefile"
	@echo "----------------------------------------"
	@echo "install      : installs required Python packages"
	@echo "run          : runs the application locally"
	@echo "docker-build : builds the docker image"
	@echo "docker-run   : runs the docker image"

install:
	@cp .env.default .env
	@source .env
	@pip install -r requirements.txt

test:
	@python run.py

run:
	@python main.py

docker-build:
	@docker build . -f ./docker/Dockerfile -t aleph-tezos-event-indexer

docker-run:
	@docker run --name aleph-tezos-event-indexer aleph-tezos-event-indexer