
.PHONY: test

test:
	@echo "Running tests..."
	@poetry run pytest tests

.PHONY: build-utils profile-utils-cprofile profile-utils-pyinstrument profile-ngrams-pyinstrument

build-utils:
	@echo "Building lib..."
	@poetry run cythonize tests/profiling/utilities.pyx 
	@poetry run python setup.py build_ext --inplace

profile-utils-cprofile: build-utils
	@echo "Profiling lib..."
	@poetry run python -m cProfile -o profile.prof tests/profiling/profile_utilities.py
	@poetry run snakeviz profile.prof

profile-utils-pyinstrument: build-utils
	@echo "Profiling lib..."
	@poetry run pyinstrument tests/profiling/profile_utilities.py

TIMESTAMP_IN_ISO_FORMAT=$(shell date -u +"%Y%m%dT%H%M%SZ")

profile-ngrams-pyinstrument:
	@echo "Profiling n-grams..."
	@mkdir -p tests/output
	@PYTHONPATH=. pyinstrument --color --show-all \
		-o tests/output\$(TIMESTAMP_IN_ISO_FORMAT)_profile_ngrams.html \
			tests/profiling/profile_ngrams.py
