
SHELL := /bin/bash
SOURCE_FOLDERS=api_swedeb penelope tests
PACKAGE_FOLDER=api_swedeb penelope 
PYTEST_ARGS=--durations=0 tests 

#--cov=$(PACKAGE_FOLDER) --cov-report=xml --cov-report=html tests
semantic-release-dryrun:
	@npx semantic-release --dry-run

.PHONY: lint tidy isort black test pylint

run:       
	@poetry run uvicorn main:app --reload

lint: tidy pylint

tidy: black isort

isort:
	@poetry run isort --profile black --float-to-top --line-length 120 --py 311 $(SOURCE_FOLDERS)

black: 
	@poetry run black --version
	@poetry run black --line-length 120 --target-version py311 --skip-string-normalization $(SOURCE_FOLDERS)

test:
	@echo "Running tests..."
	@poetry run pytest $(PYTEST_ARGS) tests

coverage:
	@echo "Running tests with coverage..."
	@poetry run pytest --durations=0 --cov=$(PACKAGE_FOLDER) --cov-report=xml --cov-report=html --cov-branch tests/ || true
.PHONY: coverage

notes:
	@poetry run pylint --notes=FIXME,XXX,TODO --disable=all --enable=W0511 -f colorized $(SOURCE_FOLDERS) || true
.PHONY: notes

pylint:
	@poetry run pylint $(SOURCE_FOLDERS)

.PHONY: tools
tools:
	@poetry self add poetry-plugin-shell poetry-plugin-export > /dev/null

requirements.txt: poetry.lock
	@poetry export --without-hashes --format=requirements.txt > requirements.txt

# requirements.txt-to-git: requirements.txt
# 	@git add requirements.txt \
# 		&& git commit -m "📌 updated requirements.txt" \
# 			&& git push

.PHONY: build-utils profile-utils-cprofile profile-utils-pyinstrument profile-ngrams-pyinstrument

build-utils:
	@echo "Building lib..."
	@poetry run cythonize tests/profiling/utilities.pyx 
	@poetry run python setup.py build_ext --inplace


profile-utils-pyinstrument: build-utils
	@echo "Profiling lib..."
	@poetry run pyinstrument tests/profiling/profile_utilities.py

TIMESTAMP_IN_ISO_FORMAT=$(shell date -u +"%Y%m%dT%H%M%SZ")

profile-kwic-pyinstrument:
	@echo "Profiling KWIC..."
	@mkdir -p tests/output
	@PYTHONPATH=. pyinstrument --color --show-all \
		-o tests/output/$(TIMESTAMP_IN_ISO_FORMAT)_profile_kwic.html \
			tests/profile_kwic.py

clean-dev:
	@rm -rf .pytest_cache build dist .eggs *.egg-info
	@rm -rf .coverage coverage.xml htmlcov report.xml .tox
	@find . -type d -name '__pycache__' -exec rm -rf {} +
	@find . -type d -name '*pytest_cache*' -exec rm -rf {} +
	@find . -type d -name '.mypy_cache' -exec rm -rf {} +
	@rm -rf tests/output

.PHONY: release publish ready build tag bump.patch guard-clean-working-repository tidy-to-git

release: ready guard-clean-working-repository bump.patch tag publish

publish:
	@poetry publish

ready: clean-dev tidy test lint requirements.txt build

build: requirements.txt
	@poetry build

tag:
	@poetry build
	@git push
	@git tag $(shell grep "^version \= " pyproject.toml | sed "s/version = //" | sed "s/\"//g") -a
	@git push origin --tags

bump.patch: requirements.txt
	@poetry version patch
	@git add pyproject.toml requirements.txt
	@git commit -m "📌 bump version patch"
	@git push

guard-clean-working-repository:
	@status="$$(git status --porcelain)"
	@if [[ "$$status" != "" ]]; then \
		echo "error: changes exists, please commit or stash them: " ; \
		echo "$$status" ; \
		exit 65 ; \
	fi
