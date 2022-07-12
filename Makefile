# collect all *.in files
REQ_IN := $(wildcard *.in)
DOCKERFILE := $(wildcard Dockerfile)
NAME = welovebot
TAG = latest

# pip requirements
REQ_OBJECTS = $(wildcard *.in)
REQ_OUTPUTS = $(REQ_OBJECTS:.in=.txt)
REQ_SYNC_TARGETS = $(REQ_OBJECTS:%.in=sync-%)
REQ_UPGRADE_TARGETS = $(REQ_OBJECTS:%.in=upgrade-%)
.PHONY: all check clean dockerenv $(REQ_SYNC_TARGETS) $(REQ_UPGRADE_TARGETS)

all: $(REQ_OBJECTS)
all: $(REQ_OUTPUTS)
all: install

%.txt: %.in
	@pip-compile -v --output-file $@ $<

dev: requirements-dev.txt

check:
	@which pip-compile > /dev/null

$(REQ_SYNC_TARGETS): sync-%: %.txt
	@pip-sync $<

$(REQ_UPGRADE_TARGETS): upgrade-%: %.in
	@pip-compile --upgrade $<

upgrade: upgrade-requirements

install: $(REQ_OUTPUTS)
	@pip install -r $<

## Git hooks
pre-commit:
	pre-commit install

dockerenv: .envrc
	: rm dockerenv
	env | grep 'NORTHISBOT' \
		| gawk ' \
			/^NORTHISBOT/ {print $$0} \
			/^export/ {print $$2} \
		' .envrc - \
		| sort -u \
		> dockerenv
	cat dockerenv

## Docker
docker-build: Dockerfile
	docker build -t $(NAME):$(TAG) -f $< .

docker-build-no-cache: Dockerfile
	docker build --no-cache -t $(NAME):$(TAG) -f $< .

docker-run: docker-build # dockerenv
	docker run \
		--env-file .env \
		-v ~/tmp/we-love-bot:/data \
		-e WELOVEBOT__CONFIG_PREFIX=WELOVEBOT \
		-e WELOVEBOT__DISCORD_TOKEN=${WELOVEBOT__DISCORD_TOKEN} \
		-p 8080:80 \
		$(NAME):$(TAG) $(ARGS)

clean: check
	-@rm -fv requirements*.txt
	find . -iname '*.pyc' -delete
