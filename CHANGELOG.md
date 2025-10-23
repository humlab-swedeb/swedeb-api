# 📦 Changelog 
[![conventional commits](https://img.shields.io/badge/conventional%20commits-1.0.0-yellow.svg)](https://conventionalcommits.org)
[![semantic versioning](https://img.shields.io/badge/semantic%20versioning-2.0.0-green.svg)](https://semver.org)
> All notable changes to this project will be documented in this file


## [0.6.0](https://github.com/humlab-swedeb/swedeb-api/compare/v0.5.1...v0.6.0) (2025-10-23)

### 🍕 Features

* add support for CWB_REGISTRY_TOKEN in Docker login process ([8bfb87d](https://github.com/humlab-swedeb/swedeb-api/commit/8bfb87df9ba70765bcdd8fe5034ae61174ff8122))

### 🐛 Bug Fixes

* force trigger release action ([d9e0276](https://github.com/humlab-swedeb/swedeb-api/commit/d9e027615a5538a00e75c607e9781429e1dcbd50))

## [0.6.0](https://github.com/humlab-swedeb/swedeb-api/compare/v0.5.1...v0.6.0) (2025-10-23)

### 🍕 Features

* add support for CWB_REGISTRY_TOKEN in Docker login process ([8bfb87d](https://github.com/humlab-swedeb/swedeb-api/commit/8bfb87df9ba70765bcdd8fe5034ae61174ff8122))

## [0.5.1](https://github.com/humlab-swedeb/swedeb-api/compare/v0.5.0...v0.5.1) (2025-10-23)

### 🐛 Bug Fixes

* add a trigger commit to kick GitHub Actions ([776df9d](https://github.com/humlab-swedeb/swedeb-api/commit/776df9d0ac56769c0587888a0561d3a69060430e))

## [0.5.0](https://github.com/humlab-swedeb/swedeb-api/compare/v0.4.0...v0.5.0) (2025-10-23)

### 🍕 Features

* add .dockerignore file to exclude unnecessary files from Docker context ([a855565](https://github.com/humlab-swedeb/swedeb-api/commit/a8555657c85b5f4f4bd40557affb4a25e9af02ab))
* add CI workflow for building and pushing to GHCR ([8205e88](https://github.com/humlab-swedeb/swedeb-api/commit/8205e885fbb4f47bce44d691bbd1fa9ed120193a))
* add Clone method to Codecs for creating a deep copy of the instance ([65a13ee](https://github.com/humlab-swedeb/swedeb-api/commit/65a13ee9b70b0e5e7f7661dccad5bb2ec9e74196))
* add comprehensive deployment guide for Swedeb API ([41b4822](https://github.com/humlab-swedeb/swedeb-api/commit/41b482262233995354000c36991c36ea78b7d0ec))
* add comprehensive Makefile documentation for building and deploying SwedeB API ([3632d94](https://github.com/humlab-swedeb/swedeb-api/commit/3632d9427567be12349b53206988c2502653989d))
* add docker-compose configuration for swedeb_api service ([2d53314](https://github.com/humlab-swedeb/swedeb-api/commit/2d533140eb4ecb22b2d27bd387cdfcfcf429c0ac))
* add Dockerfile, Makefile, and README for CWB container setup ([09d93d4](https://github.com/humlab-swedeb/swedeb-api/commit/09d93d431146b508cd9b62d2480794aeb9fef2dd))
* add expected response format for word trends test case ([856bd60](https://github.com/humlab-swedeb/swedeb-api/commit/856bd60c7620bf85800d334c3fef7c2c05b2058f))
* add fixture for codecs speech index source dictionary ([1aa5246](https://github.com/humlab-swedeb/swedeb-api/commit/1aa524687c9d0d7925546121254a3c578bcbf6b1))
* add improved filtering function for speakers based on selection criteria (not used for now) ([44dfe61](https://github.com/humlab-swedeb/swedeb-api/commit/44dfe617427fdd80d27ed8766e2867047ab745bd))
* add Makefile for Docker/Podman build and deployment process ([3e20f3a](https://github.com/humlab-swedeb/swedeb-api/commit/3e20f3a00bdb40428ec63bfbb81fb1a8be51efcb))
* add Python setup and install Poetry in release workflow; update package dependencies ([f0548d8](https://github.com/humlab-swedeb/swedeb-api/commit/f0548d8eaeaca3b179be088bea42a3916d544dd4))
* add release dry run targets and prepare release assets script ([d613d24](https://github.com/humlab-swedeb/swedeb-api/commit/d613d24c458d9e639a366eaa9f897d5fa9c634e3))
* add reverse method to Codec for obtaining reversed codec mappings ([d0c7519](https://github.com/humlab-swedeb/swedeb-api/commit/d0c7519d3e2094afbe3afaa1fbe1956bde3b4a19))
* add runlike scripts and update compose files for swedeb_api service ([0f0776e](https://github.com/humlab-swedeb/swedeb-api/commit/0f0776e39678f0acb7b6f2544b7d0dece38d5bbb))
* add scripts for preparing release assets and publishing Docker images ([ef84d8b](https://github.com/humlab-swedeb/swedeb-api/commit/ef84d8bef5653ce7b37fac11d9dc0e58f14c0a48))
* add semantic-release dry run target to Makefile ([05f827b](https://github.com/humlab-swedeb/swedeb-api/commit/05f827b1e13c8a3b5ff78edd43f179e2c14c33eb))
* add SubOfficeRenameHook to rename column in sub_office_type and update mapping in SpeechTextRepository ([2899766](https://github.com/humlab-swedeb/swedeb-api/commit/289976658e1f298204dca401872420aa1f90c1e2))
* add table attribute to Codec class for improved data handling ([508ef7d](https://github.com/humlab-swedeb/swedeb-api/commit/508ef7df6300afbd89e02e72d16b63781823ffbd))
* enhance load method to trigger on-load hooks ([e63dcf2](https://github.com/humlab-swedeb/swedeb-api/commit/e63dcf24e0f8e75b902959da4b03e48754d88bde))
* enhance Makefile for Docker/Podman integration and improve environment checks ([962a127](https://github.com/humlab-swedeb/swedeb-api/commit/962a1278bbbffeb31033369a7c112bf0e753ffb0))
* enhance release process with version synchronization and simplified workflow ([1c2db0f](https://github.com/humlab-swedeb/swedeb-api/commit/1c2db0feadb3ed31ffc095c97cabdc3c3dd2aba0))
* overhaul README to detail environment management and deployment strategies using Docker and Docker Compose ([cbf1f03](https://github.com/humlab-swedeb/swedeb-api/commit/cbf1f03741885c68e0a563150ee86bcac4ef3100))
* restore 'pid' column for indexed retrieval of person by iloc (needed for property value specs) ([4061a35](https://github.com/humlab-swedeb/swedeb-api/commit/4061a35c58ae4c3a1f27063f67e7411632d0a50f))
* restructure README to enhance clarity on project setup, technology stack, and automated release workflow ([11a6cd6](https://github.com/humlab-swedeb/swedeb-api/commit/11a6cd6f9f585eb40bdf2f4f2034fa61c44afdb1))
* update Docker Compose configuration to include metadata volume and remove unused IPAM settings ([1737065](https://github.com/humlab-swedeb/swedeb-api/commit/1737065de5822badffb98b3d07be7b106fca2a73))
* update Makefile used in development ([1514f8f](https://github.com/humlab-swedeb/swedeb-api/commit/1514f8f7b176bc4da00a9489faf78212ced1a805))
* update type hint for rev_mapping and improve test case description ([2aaca3f](https://github.com/humlab-swedeb/swedeb-api/commit/2aaca3f6dcc91125fd69ec56421cae60609145b6))

### 🐛 Bug Fixes

*  rename context_width to context_size ([6d1dd6b](https://github.com/humlab-swedeb/swedeb-api/commit/6d1dd6b81027bd5f39becdb95135b4ff0284f6e6))
* add docstring to to_cqp_criteria_expr ([70840bc](https://github.com/humlab-swedeb/swedeb-api/commit/70840bc85e460ad8ad1b26da0c1da465e0983f5a))
* add missing function, docstring and missing import ([7d6d40c](https://github.com/humlab-swedeb/swedeb-api/commit/7d6d40c064d913041f8fb71c109ae948fa358a70))
* add missing import for loguru logger ([f4d1694](https://github.com/humlab-swedeb/swedeb-api/commit/f4d1694f8475ae0315b21121a19df5847c3c8764))
* add sys import and configure logger for better error diagnostics ([e29ffbe](https://github.com/humlab-swedeb/swedeb-api/commit/e29ffbefc39ce5779f0339ac0dd89d83c9077b00))
* clean up imports and formatting in test files ([59578e9](https://github.com/humlab-swedeb/swedeb-api/commit/59578e9bb12c76f03ba5c182dbeff2cdc768ae89))
* correct value_updates structure in test_decode_speech_index ([9731b85](https://github.com/humlab-swedeb/swedeb-api/commit/9731b8514c01701d8314a9ca8ee987501de105fc))
* handle None case for persons_of_interest in MultiplePartyAbbrevsHook ([f72d99e](https://github.com/humlab-swedeb/swedeb-api/commit/f72d99e625cf1fd1e41e70d7fca1d16ba7cb10fd))
* phony typo in in Makefile ([cb301d1](https://github.com/humlab-swedeb/swedeb-api/commit/cb301d184e63ecf590110fc11a966ec5bbf303a8))
* refactor speech_link method to use config value ([1e3c068](https://github.com/humlab-swedeb/swedeb-api/commit/1e3c068f4511ed1e01152fe7b23f542b5f7f7ae1))
* remove deprecated staging environment configuration file ([52a42e3](https://github.com/humlab-swedeb/swedeb-api/commit/52a42e33ecd77368540fe73e18b69a0aea159c3e))
* remove redundant 'pid' from ignores in person_codecs decode method ([87818aa](https://github.com/humlab-swedeb/swedeb-api/commit/87818aa921e2e51c772ba4267f5c683fa2d4ebee))
* remove redundant import of loguru in conftest.py ([c9fc880](https://github.com/humlab-swedeb/swedeb-api/commit/c9fc88046ae94c99d1e21b42f55531448bba0e43))
* remove redundant method call in person_codecs2 fixture and clean up commented-out 'pid' in fixture_source_dict ([2f8818a](https://github.com/humlab-swedeb/swedeb-api/commit/2f8818a5ebc16008dc8f1718d9a2f2d0b4a2b005))
* remove redundant test ([563b059](https://github.com/humlab-swedeb/swedeb-api/commit/563b05973dd473ad72fee864074f588a592f58bb))
* remove unused import of BaseCodecs from test_codecs.py ([b5b08b0](https://github.com/humlab-swedeb/swedeb-api/commit/b5b08b0f92f204c6055e0a54f60c68af0a448212))
* remove unused imports and clean up test function signatures ([37cac95](https://github.com/humlab-swedeb/swedeb-api/commit/37cac95162204b4ffde663fd3232423d30ae7daa))
* rename fixture 'source_dict' to 'codecs_source_dict' for clarity ([64af531](https://github.com/humlab-swedeb/swedeb-api/commit/64af5311fcbb34188d0d08905e6c4ec8ab392697))
* reorder installation steps for semantic-release in release workflow ([de67aeb](https://github.com/humlab-swedeb/swedeb-api/commit/de67aebcac88dfcefc8ab37f88013dbc719a3ba0))
* resolves Strange word trend measures ([3d4c6a2](https://github.com/humlab-swedeb/swedeb-api/commit/3d4c6a22d5b12514839a33bd0a11a7ef8697a740)), closes [#204](https://github.com/humlab-swedeb/swedeb-api/issues/204)
* restore missing values mapping in Codec property property_values_specs. ([1aa3b24](https://github.com/humlab-swedeb/swedeb-api/commit/1aa3b2462e0916d558065e7f233c6545954ea932))
* skip test for phrase handling in n-grams ([af9d703](https://github.com/humlab-swedeb/swedeb-api/commit/af9d703b7dde4c8dfe3e3861bb3bd2d8ad464846))
* update CI workflow to use Docker Buildx and remove Podman installation steps ([7318367](https://github.com/humlab-swedeb/swedeb-api/commit/7318367878621bf45cc66aae93c23178659ba81f))
* update dependency versions and remove obsolete tomli package from poetry.lock ([9e76ba4](https://github.com/humlab-swedeb/swedeb-api/commit/9e76ba4b455e0611b92d41ec294699089ef6a8ec))
* update Dockerfile to correct wheel installation paths and cleanup ([c1cca02](https://github.com/humlab-swedeb/swedeb-api/commit/c1cca023bff0a35e12a6214bbf992160a11bd625))
* update keyword string format in test_compute_n_grams2 ([aa22396](https://github.com/humlab-swedeb/swedeb-api/commit/aa22396fa9e6eb677f67a54311bd05e34a7a09f3))
* update parameter names for clarity in n_grams function ([265b91b](https://github.com/humlab-swedeb/swedeb-api/commit/265b91b8ca69a782714c2c6c91771d636da7552d))
* update Python version constraints and tool configurations in pyproject.toml ([b6c2fa5](https://github.com/humlab-swedeb/swedeb-api/commit/b6c2fa5196d8b9fd31c1ba819d0f2fe22bb3be68))
* update retrieval of mappings to use get_mapping method ([03a3c81](https://github.com/humlab-swedeb/swedeb-api/commit/03a3c811aa55a9dfdbbb7f6d83f728cff6a6df78))
* validate query_or_opts type and handle None in query_keyword_windows ([ad03d33](https://github.com/humlab-swedeb/swedeb-api/commit/ad03d33a523b391c83d54303d494b1d468d61c3d))

### 📝 Documentation

* update README with environment management and deployment strategy ([f37e0ef](https://github.com/humlab-swedeb/swedeb-api/commit/f37e0ef10945033d70ae23d601b5671a574337cc))

### 🧑‍💻 Code Refactoring

* clean up whitespace and improve code readability in codecs and utility modules ([086fdd7](https://github.com/humlab-swedeb/swedeb-api/commit/086fdd7f6bf9b3e45493d9d6da6e88a46aeb0085))
* codec class changes ([26650ff](https://github.com/humlab-swedeb/swedeb-api/commit/26650ff8325e0535a6c1d87dc165445e04fab73b))
* enhance apply method in Codec class ([291e343](https://github.com/humlab-swedeb/swedeb-api/commit/291e343d658eb940f8c7e8c2b896af1eb5ca730e))
* enhance load method for better handling of data sources and improve table assignment ([83b5b26](https://github.com/humlab-swedeb/swedeb-api/commit/83b5b2633a39f523afd14da0de2ac500730ff9c7))
* improve logic for loading tables from Sqlite. ([5a76d39](https://github.com/humlab-swedeb/swedeb-api/commit/5a76d396d4ca01f3809ebd46a733f1f116621ddc))
* make testing more robust by using method scoped test fixture for speech index and person codecs ([a6e5e26](https://github.com/humlab-swedeb/swedeb-api/commit/a6e5e2601f15d830cc130612002f455e8d146a8b))
* remove commented-out IPAM configuration from compose.yml ([3f62abb](https://github.com/humlab-swedeb/swedeb-api/commit/3f62abb4a1cb224874b8418534e9f21b0b2a2d88))
* remove obsolete test file for person codecs ([2993246](https://github.com/humlab-swedeb/swedeb-api/commit/299324684e7a63cea7374fc52629e39610037e1e))
* remove redundant method call in PersonCodecs initialization ([c3c02dc](https://github.com/humlab-swedeb/swedeb-api/commit/c3c02dccf29ae74d89dde23ca9c09b3d4f2a9cee))
* rename BaseCodecs to Codecs and update related tests ([801e531](https://github.com/humlab-swedeb/swedeb-api/commit/801e531122fd79f426e9df9b826ca0d50a6c5bd5))
* restore legacy codec tests ([6b60f7e](https://github.com/humlab-swedeb/swedeb-api/commit/6b60f7e2350ae894f896abfd170359cc41671b36))
* simplify codecs classes andreduce hard-coding ([b6eb960](https://github.com/humlab-swedeb/swedeb-api/commit/b6eb9604bf7d622ac03f3aa81205fd858aecc96a))
* simplify Dockerfile by using GHRC images ([945c8a4](https://github.com/humlab-swedeb/swedeb-api/commit/945c8a4d807d2c0310cb7c56db0747be987df17e))
* standardize method naming and enhance documentation in codecs and utility modules ([1658af2](https://github.com/humlab-swedeb/swedeb-api/commit/1658af2b7304542760f6b7fcdf3b765098b8b9b6))
* updated codecs unit tests with better mocking and isolation ([8539471](https://github.com/humlab-swedeb/swedeb-api/commit/8539471c0447ac8fa2ae1f1f637f3b68ed4cff16))
* use index for faster filtering (assume "person_id" is index) ([b25e8c1](https://github.com/humlab-swedeb/swedeb-api/commit/b25e8c1fefad599d035f4df20aa6e90c7055c708))

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
