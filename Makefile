# collect all *.in files
REQ_IN := $(wildcard *.in)
DOCKERFILE := $(wildcard Dockerfile)
NAME = northisbot
TAG = latest

# generate *.txt file names from *.in name
REQ_TXT = $(REQ_IN:%.in=%.txt)
PIP_INSTALL = $(REQ_IN:%.in=%)

bootstrap:
bootstrap: pre-commit pip-install

pre-commit:
	pre-commit install

# rule to match any *.txt requirement and install it
$(REQ_TXT): %.txt: %.in
	echo "Call pip-compile to generate $@ from $<"
	pip-compile $< --output-file $@
	pip install -r $@

pip-$(PIP_INSTALL): %: %.in
	pip install -r $<

install: requirements.txt
	pip install -r $<

pip-install-test: requirements-test.txt
	pip install -r $<

docker-build: Dockerfile
	docker build -t $(NAME):$(TAG) -f $< .

run: docker-build
	docker run \
		-e DISCORD_NORTHISBOT_TOKEN=${DISCORD_NORTHISBOT_TOKEN} \
		-e NORTHISBOT__INCOMING_WEB_HOOKS__HOST=0.0.0.0 \
		-e NORTHISBOT__INCOMING_WEB_HOOKS__PORT=8080 \
		-p 8080:80 \
		$(NAME):$(TAG)

dev: requirements-dev.txt
test: requirements-test.txt

clean:
	/bin/rm -fv requirements*.txt
	find . -iname '*.pyc' -delete

all: run
.PHONY: all requirements.txt docker-build
