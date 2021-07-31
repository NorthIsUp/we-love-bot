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
.PHONY: all check clean $(REQ_SYNC_TARGETS) $(REQ_UPGRADE_TARGETS)

all: $(REQ_OBJECTS)
all: $(REQ_OUTPUTS)
all: install

%.txt: %.in
	@pip-compile -v --output-file $@ $<

dev.txt: main.txt

check:
	@which pip-compile > /dev/null

$(REQ_SYNC_TARGETS): sync-%: %.txt
	@pip-sync $<

$(REQ_UPGRADE_TARGETS): upgrade-%: %.in
	@pip-compile --upgrade $<

upgrade-dev: upgrade-main

install: $(REQ_OUTPUTS)
	@pip install -r $<

## Git hooks
pre-commit:
	pre-commit install

## Docker
docker-build: Dockerfile
	docker build -t $(NAME):$(TAG) -f $< .

docker-build-no-cache: Dockerfile
	docker build --no-cache -t $(NAME):$(TAG) -f $< .


docker-run: docker-build
	docker run \
		-e WELOVEBOT__CONFIG_PREFIX=WELOVEBOT \
		-e WELOVEBOT__DISCORD_TOKEN=${WELOVEBOT__DISCORD_TOKEN} \
		-e WELOVEBOT__INCOMING_WEB_HOOKS__HOST=0.0.0.0 \
		-e WELOVEBOT__INCOMING_WEB_HOOKS__PORT=8080 \
		-p 8080:80 \
		$(NAME):$(TAG)

clean: check
	-@rm -fv requirements*.txt
	find . -iname '*.pyc' -delete
