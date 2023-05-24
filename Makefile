help:
	@echo "This is the help for the Makefile"

install:
	@cp .env.default .env
	@source .env
	@pip install --upgrade pip==23.1.2
	@pip install -r requirements.txt

test:
	@python run.py

run:
	@python main.py

run-docker:
	@docker-compose -f docker/docker-compose.yaml up