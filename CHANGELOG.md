# 📦 Changelog 
[![conventional commits](https://img.shields.io/badge/conventional%20commits-1.0.0-yellow.svg)](https://conventionalcommits.org)
[![semantic versioning](https://img.shields.io/badge/semantic%20versioning-2.0.0-green.svg)](https://semver.org)
> All notable changes to this project will be documented in this file


## [0.4.0](https://github.com/humlab-swedeb/swedeb-api/compare/v0.3.0...v0.4.0) (2025-06-10)

### 🍕 Features

* add initial configuration file for version 1.1.0 ([8a0cba9](https://github.com/humlab-swedeb/swedeb-api/commit/8a0cba92b7ff0e847817a87cdb9c824dca61424a))
* added Speech DTO class to API/core (dict-like class) ([fbdaf0c](https://github.com/humlab-swedeb/swedeb-api/commit/fbdaf0ce2ef00839976502d29ccbb7e5d26cd1a0))
* restructure Docker Compose files for production and staging environments ([7908005](https://github.com/humlab-swedeb/swedeb-api/commit/7908005752fcff99bef19b6be2f37386e3b5eec9))

### 🐛 Bug Fixes

* add logging for registry directory in get_cwb_corpus function ([33fcc13](https://github.com/humlab-swedeb/swedeb-api/commit/33fcc137048900130546922e8d85e755098e105f))
* address FIXME regarding HTTPException handling in speech download endpoint. Ref [#106](https://github.com/humlab-swedeb/swedeb-api/issues/106) ([3418f4e](https://github.com/humlab-swedeb/swedeb-api/commit/3418f4e146e94f7f71c9af15098c025b90ce6a15))
* correcting pdf links with tests ([47c54e5](https://github.com/humlab-swedeb/swedeb-api/commit/47c54e53cc389a14a1c7db51871aae5a2708f5c6))
* ensure create-tmpdir is a prerequisite for frontend target ([626a0d3](https://github.com/humlab-swedeb/swedeb-api/commit/626a0d3383f91b0cb6a847d98c2fbcaf7a539cf3))
* fetch page number from speech instead of from first utterance in protocol ([142bd71](https://github.com/humlab-swedeb/swedeb-api/commit/142bd717245bd670279724d12b4dc29d6450df91))
* fix for too many ngrams windows with phrases ([ee29f6b](https://github.com/humlab-swedeb/swedeb-api/commit/ee29f6baa6d39db9a0d226839492fce5e3773a85))
* fix test failures caused by lazy fixture ([559215f](https://github.com/humlab-swedeb/swedeb-api/commit/559215f135295185f2984cd4718829298c7d72c4))
* fixed release workflow permissions ([8dc7a25](https://github.com/humlab-swedeb/swedeb-api/commit/8dc7a2582b9183a8a392ddf4216b0ef7d66a74f2))
* fixed tests that failed due to lazy fixture initialization ([ae5e6f4](https://github.com/humlab-swedeb/swedeb-api/commit/ae5e6f405ef83ced97b214475bfb86c7324524fe))
* introduce SWEDEB_BACKEND_SOURCE enabling build from git, pypi or workdir ([13f6d9e](https://github.com/humlab-swedeb/swedeb-api/commit/13f6d9eb0f4583547e37063eb8218254237e00b4))
* remove commented-out code for streamify_source and PropsMixIn class ([923b80b](https://github.com/humlab-swedeb/swedeb-api/commit/923b80b061debc581eae428753713fd3ede86327))
* remove redundant target from frontend and clean up create-tmpdir ([6cc742b](https://github.com/humlab-swedeb/swedeb-api/commit/6cc742bfa61839e0f845fb26b105286b626dd427))
* return kwic results for non-party data ([58e6869](https://github.com/humlab-swedeb/swedeb-api/commit/58e6869a204309244ee2b539aa8ab186e55e50ff))
* simplify Dockerfile by removing unnecessary symlink for registry ([b4abf4c](https://github.com/humlab-swedeb/swedeb-api/commit/b4abf4cecb8a4d96466a1d6390a8d9caf3d89831))
* update backend installation logic to support pypi source ([76e0bac](https://github.com/humlab-swedeb/swedeb-api/commit/76e0bac0f28dc6c05b7f6ba0204dffff25134f04))
* update Docker Compose configuration for production and add new compose file for riksdagsdebatter.se ([2502a50](https://github.com/humlab-swedeb/swedeb-api/commit/2502a502eabad08ba19307112758865830636a55))
* update docker compose file references in Makefile (renamed compose file) ([40e02bc](https://github.com/humlab-swedeb/swedeb-api/commit/40e02bca392c13a0164fcdff427cdbb733fc0edc))
* update fillna usage to avoid future warnings in codecs and utility modules ([99a240e](https://github.com/humlab-swedeb/swedeb-api/commit/99a240ec37075a5b2c2e3895b28b441290f0d93b))
* update frontend tag check to include 'workdir-dist' option ([603d7e1](https://github.com/humlab-swedeb/swedeb-api/commit/603d7e1f8e0ab4f76457386b3f0107f8dafd634c))
* update HOME path in riksprot_corpus registry entry ([77b228b](https://github.com/humlab-swedeb/swedeb-api/commit/77b228bb0b1bcffaac4dd2ab02e6445e48ce8a6f))
* update test data caused by regressions in expected ([17b8df3](https://github.com/humlab-swedeb/swedeb-api/commit/17b8df38a5fda2759e2f298293c246b9225139f7))
* update version and dependencies in pyproject.toml ([f9282dc](https://github.com/humlab-swedeb/swedeb-api/commit/f9282dc75999f03e5d2bac39fe63428d4593d987))

### 🧑‍💻 Code Refactoring

* remove unused Registry class from penelope utility ([80f7d1a](https://github.com/humlab-swedeb/swedeb-api/commit/80f7d1aa0490b2c8bfa7fa3fa9dce8822be9a021))
* removed additional penelope related files not used by swedeb. ([256745e](https://github.com/humlab-swedeb/swedeb-api/commit/256745ee2ce3e4cc486b1270a7e09ff745957d5b))
* update folder structure and metadata versions in config.yml ([a1c2eb7](https://github.com/humlab-swedeb/swedeb-api/commit/a1c2eb7608f9e3bcf5530973745f5d67274daf64))

### ✅ Tests

* add comprehensive tests for tool router endpoints. Ref [#105](https://github.com/humlab-swedeb/swedeb-api/issues/105) ([3655e36](https://github.com/humlab-swedeb/swedeb-api/commit/3655e3666a66c53131300177e190191479c75fcd))
* add speech index test ([049e14f](https://github.com/humlab-swedeb/swedeb-api/commit/049e14f4eccb2cdea8806b3bddacf568b1c20d7f))
* added unit test for get_speech ([3d0a9ea](https://github.com/humlab-swedeb/swedeb-api/commit/3d0a9ea9474d2a59d7ca485f4bfa576942c8e05e))
* de-skipped working tests ([e0e7eec](https://github.com/humlab-swedeb/swedeb-api/commit/e0e7eec002ec711f5c36af4dd91d10f564b0f199))
* enhance tool router tests with additional fixtures and cleanup. Ref [#105](https://github.com/humlab-swedeb/swedeb-api/issues/105) ([f468958](https://github.com/humlab-swedeb/swedeb-api/commit/f468958b25b1662178491a1690ecbb746601786f))
* implement tests for speech download endpoint with valid and invalid speech IDs. Ref [#105](https://github.com/humlab-swedeb/swedeb-api/issues/105) ([4a3842a](https://github.com/humlab-swedeb/swedeb-api/commit/4a3842a519a7f8c146ddeff84f80c650c4f99cf8))

##  (2025-04-19)

### Features

* add ignore (target) columns when applying codecs ([5dfab32](https://github.com/humlab-swedeb/swedeb-api/commit/5dfab32aa0c4a3ea1eb75a1cbc195c130508f170))
* implemented KWIC/n-gram chamber_abbrev filter ([#101](https://github.com/humlab-swedeb/swedeb-api/issues/101)) ([8dc4205](https://github.com/humlab-swedeb/swedeb-api/commit/8dc4205b57c4ed2747594159eb398bf2bf1c591c))

### Bug Fixes

* handle empty chamber values (related to [#101](https://github.com/humlab-swedeb/swedeb-api/issues/101)) ([65ac458](https://github.com/humlab-swedeb/swedeb-api/commit/65ac4580ee9a777e1cbdf18bf7aafb5cc79c99db))
* improve generation of document names for grouped data ([7fde733](https://github.com/humlab-swedeb/swedeb-api/commit/7fde7331bcbc2e6f80c77678ff799352b3f5a28f))
* Resolves [#133](https://github.com/humlab-swedeb/swedeb-api/issues/133) ([ce2aa11](https://github.com/humlab-swedeb/swedeb-api/commit/ce2aa112b1d138d763d9287dbf387cc35de87265))
## [0.2.1](https://github.com/humlab-swedeb/swedeb-api/compare/0.1.1...0.2.1) (2025-01-22)

### Features

* add resolve method to CommonQueryParams for default value handling (only used in tests) ([dc711e7](https://github.com/humlab-swedeb/swedeb-api/commit/dc711e7db6979f7a229f4a89cccefb153a3819ab))

### Bug Fixes

* add PYDEVD_WARN_EVALUATION_TIMEOUT to launch configuration ([ea0d00a](https://github.com/humlab-swedeb/swedeb-api/commit/ea0d00a18d025ae4bd546d2600bdf90da8bfa619))
* update dotset function to handle underscores in path ([c624822](https://github.com/humlab-swedeb/swedeb-api/commit/c6248227e97400672e22210d91c475d38e00360c))
* update failing recipi (requirements.txt) ([48badff](https://github.com/humlab-swedeb/swedeb-api/commit/48badffc0fa4ac8aca5d04c38ae1b8b88665189d))
* update remember method to use keyword argument for words per year ([d74047c](https://github.com/humlab-swedeb/swedeb-api/commit/d74047ce1fab5eab4fe2ab738d1d91845290ddce))
## [0.1.1](https://github.com/humlab-swedeb/swedeb-api/compare/041a04dd7c04ce304ec8236b36e049dbcf97c14a...0.1.1) (2024-10-15)

### Features

* add decode_speech_index method to process and standardize speech index data ([ad6811e](https://github.com/humlab-swedeb/swedeb-api/commit/ad6811ea20fb97060934ea720655dcf3574e0391))
* add functions to load and slim speech index from DTM corpus ([daccae9](https://github.com/humlab-swedeb/swedeb-api/commit/daccae9c0b59499357d79d2abdb326664d9cdbd2))
* add indexing function that accepts all person ids ([7f5a4a4](https://github.com/humlab-swedeb/swedeb-api/commit/7f5a4a422f0288cbc53bd8683ceee8f8fa11c207))
* add pytest fixtures for API corpus and related data structures ([2291071](https://github.com/humlab-swedeb/swedeb-api/commit/2291071cb611567b7b27fce7852f35a8212de646))
* Add utility functions for lazy evaluation ([041a04d](https://github.com/humlab-swedeb/swedeb-api/commit/041a04dd7c04ce304ec8236b36e049dbcf97c14a))
* added improved fetch speech methods ([e7c96fe](https://github.com/humlab-swedeb/swedeb-api/commit/e7c96fee297baf27719a45e0e1cb706ecf7d6a7d))
* added time-it decorator ([1aa30ed](https://github.com/humlab-swedeb/swedeb-api/commit/1aa30ed4b950a3528d8cbed5051376b5a3d93b0f))
* allow alternativ key ([56b01de](https://github.com/humlab-swedeb/swedeb-api/commit/56b01de64ee132022a553ea6e824cb2324c8149d))
* change _get_speech_info to accept different ids ([720e1cf](https://github.com/humlab-swedeb/swedeb-api/commit/720e1cf14c61a4b4de5453188f3f6ab541772c0b))
* enhance ngrams_to_ngram_result to support custom separator and document splitting ([50a8d58](https://github.com/humlab-swedeb/swedeb-api/commit/50a8d58f277199f80aa73a5791b61947c16acf15))
* n-gram alignment ([611d955](https://github.com/humlab-swedeb/swedeb-api/commit/611d95592d1066f312dc4debc61f8190126cba7d)), closes [#18](https://github.com/humlab-swedeb/swedeb-api/issues/18)
* refactor get_anforanden_for_word_trends to use get_speeches_by_words for improved speech retrieval ([3da278f](https://github.com/humlab-swedeb/swedeb-api/commit/3da278f64943674471123be188297bdb845f9c15))
* refeacter get_anforanden method to use get_speeches_by_opts ([2d649cd](https://github.com/humlab-swedeb/swedeb-api/commit/2d649cdfbe9d47ff0555d11c8157d3cc53b567ef))
* resolves [#54](https://github.com/humlab-swedeb/swedeb-api/issues/54) ([9f30bd9](https://github.com/humlab-swedeb/swedeb-api/commit/9f30bd9cc9bf85715275cec61374b1fe7e7ad136))
* update person_wiki_link to handle unknown wiki IDs and return localized string ([cd27159](https://github.com/humlab-swedeb/swedeb-api/commit/cd27159d78b511885f0c72a821f4efd143c63f9a))

### Bug Fixes

* fixed recepi ([817f265](https://github.com/humlab-swedeb/swedeb-api/commit/817f265e10a74ce8b97de0c961050ba7f9ca3fed))
* improve error handling for missing speech files ([dc71d73](https://github.com/humlab-swedeb/swedeb-api/commit/dc71d73ab3301d5c60fedc7708b2d31e58bd6806))
* lock association-measures to resolve cwb-ccc dependency conflict ([2b623d6](https://github.com/humlab-swedeb/swedeb-api/commit/2b623d6bef460fd660315c817ef958c75a8693dd))
* update test assertion for word trend results ([522c71f](https://github.com/humlab-swedeb/swedeb-api/commit/522c71f7d717a6056736823171e018e06780f65d))
