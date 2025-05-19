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
