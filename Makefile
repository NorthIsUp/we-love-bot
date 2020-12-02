# collect all *.in files
REQ_IN := $(wildcard *.in)
DOCKERFILE := $(wildcard Dockerfile)
NAME = northisbot
TAG = latest

# generate *.txt file names from *.in name
REQ_TXT = $(REQ_IN:%.in=%.txt)

bootstrap:
bootstrap: pre-commit pip-install

pre-commit:
	pre-commit install

# rule to match any *.txt requirement and install it
$(REQ_TXT): %.txt: %.in
	echo "Call pip-compile to generate $@ from $<"
	pip-compile $< --output-file $@
	pip install -r $@

pip-install-test: requirements-test.txt
	pip install -r $<

docker-build: Dockerfile
	docker build -t $(NAME):$(TAG) -f $< .

run: docker-build
	docker run $(NAME):$(TAG)

dev: requirements-dev.txt
test: requirements-test.txt

clean:
	/bin/rm -fv requirements*.txt
	find . -iname '*.pyc' -delete

all: run
.PHONY: all requirements.txt docker-build
