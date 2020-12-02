# collect all *.in files
REQ_IN := $(wildcard *.in)

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

docker: Dockerfile
	docker build --pull --rm -f Dockerfile -t northisbot:latest "."

run: requirements.txt
	echo "+ running"
	./entrypoint.sh

dev: requirements-dev.txt
test: requirements-test.txt

clean:
	/bin/rm -fv requirements*.txt
	find . -iname '*.pyc' -delete

all: run
.PHONY: all requirements.txt
