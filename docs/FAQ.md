Replace `swedeb_staging` with the deploy environment you want are working with.

## How do I enter Quadlet shell?

```bash
user@pdf-server:~# sudo su -
root@pdf-server:/srv/swedeb_staging# cd /srv/swedeb_staging
root@pdf-server:/srv/swedeb_staging# manage-quadlet shell
```

## Update Quadlet configuration

The Swedeb Quadlet container files are version controlled in the backend's docker folder/quadlets. Please make changes to these files, then copy then to the target environment.

```bash
swedeb_staging@you:~$ scp -R youruser@mydevserver:/path/to/quadlets .
swedeb_staging@you:~$ scp youruser@mydevserver:/path/to/config.yml config.yml
swedeb_staging@you:~$ sudo cp quadlets/* /srv/swedeb_staging/configuration/quadlets
swedeb_staging@you:~$ sudo chown -R swedeb_staging:swedeb_staging /srv/swedeb_staging/configuration/quadlets
swedeb_staging@pdf-server:~$ manage-quadlet install
```
Or manual emergency edit:
```bash
swedeb_staging@pdf-server:~$ vi configuration/quadlets/swedeb-staging-app.container
swedeb_staging@pdf-server:~$ manage-quadlet remove
swedeb_staging@pdf-server:~$ manage-quadlet install
```

## How do I update Swedeb image on PDF-server?

Enter Quadlet shell, then:

```bash
swedeb_staging@pdf-server:~$ podman image pull ghcr.io/humlab-swedeb/swedeb-api:staging
manage-quadlet remove
manage-quadlet install
```

Replace `staging` with the version you want to update (e.g. `latest` or specific version)

## How do I open a shell in a container?

Enter Quadlet shell, then:

```bash
swedeb_staging@pdf-server:~$ podman ps
#  ---> find container and it's ID xyz
swedeb_staging@pdf-server:~$ podman exec -it "xyz" /bin/bash
```

---

## What data does a running Swedeb API instance use?

All paths resolve from `config/config.yml` (config key shown in parentheses).

### 1. Speech Index (Document Index)

**Purpose**: In-memory DataFrame of all speeches — the primary filter/join table used by every query.  
**Config**: `dtm.folder` + `dtm.tag` (currently `dtm.folder=/data/swedeb/v1.1.0/dtm/text`, `dtm.tag=text`)

| Priority        | File                                                    | Notes                       |
|-----------------|---------------------------------------------------------|-----------------------------|
| 1st (preferred) | `{dtm.folder}/{dtm.tag}_document_index.prepped.feather` | Slimmed+typed feather cache |
| 2nd             | `{dtm.folder}/{dtm.tag}_document_index.feather`         | Raw feather                 |
| 3rd (fallback)  | `{dtm.folder}/{dtm.tag}_document_index.csv.gz`          | Original source             |

Writes `.prepped.feather` on first load from feather/CSV. See `api_swedeb/core/load.py::load_speech_index()`.

### 2. Document-Term Matrix (VectorizedCorpus / DTM)

**Purpose**: Sparse term-frequency matrix backing word trends and n-gram queries.  
**Config**: `dtm.folder`, `dtm.tag`

| File                                                   | Notes                                                |
|--------------------------------------------------------|------------------------------------------------------|
| `{dtm.folder}/{dtm.tag}_vector_data.npz` **or** `…npy` | The document-term matrix — `.npz` or `.npy`          |
| `{dtm.folder}/{dtm.tag}_vectorizer_data.pickle`        | Vocabulary (`token2id`), doc index, term frequencies |
| `{dtm.folder}/{dtm.tag}_document_index.csv.gz`         | Document index (if not loaded separately)            |
| `{dtm.folder}/{dtm.tag}_overridden_term_frequency.npy` | Optional TF override                                 |

Only loaded on first word-trends or n-gram request (lazy). See `api_swedeb/core/load.py::load_dtm_corpus()`.

The document-term matrix — exactly one format is present. `.npz` is a sparse CSR matrix (default, built with `compressed=True`); `.npy` is a dense numpy array (legacy, built with `compressed=False`). Load code tries `.npz` first, falls back to `.npy`.

### 3. Metadata SQLite Database (PersonCodecs)

**Purpose**: Code tables for decoding integer IDs to human-readable labels (party, gender, chamber, etc.) and the full `persons_of_interest` speaker manifest.  
**Config**: `metadata.filename` → `/data/swedeb/v1.1.0/riksprot_metadata.db`

Tables loaded via `PersonCodecs` (declared in `config.yml → mappings.tables`):

| Table                 | Primary key          |
|-----------------------|----------------------|
| `chamber`             | `chamber_id`         |
| `gender`              | `gender_id`          |
| `government`          | `government_id`      |
| `office_type`         | `office_type_id`     |
| `party`               | `party_id`           |
| `sub_office_type`     | `sub_office_type_id` |
| `persons_of_interest` | `person_id`          |
| `person_party`        | `person_party_id`    |

Table accessed directly by the speech text backends (outside `PersonCodecs`):

| Table           | Columns used                      | Access point |
|-----------------|-----------------------------------|--------------|
| `speaker_notes` | `speaker_note_id`, `speaker_note` | `SpeechRepositoryFast._speaker_note_id2note` (prebuilt backend) and `SpeechTextRepository.speaker_note_id2note` (legacy backend) — lazy-loaded on first speech retrieval |

See `api_swedeb/core/codecs.py::PersonCodecs`, `api_swedeb/core/speech_repository_fast.py`, `api_swedeb/legacy/speech_lookup.py`.

### 4. CWB Corpus (KWIC and N-grams)

**Purpose**: Positionally-indexed word corpus queried via CQP for keyword-in-context and n-gram analysis.  
**Config**: `cwb.registry_dir`, `cwb.corpus_name`

| Resource              | Location                                                                           |
|-----------------------|------------------------------------------------------------------------------------|
| Registry file         | `{cwb.registry_dir}/{cwb.corpus_name}` (e.g. `/some-path/registry/RIKSPROT_PROT`) |
| Corpus data directory | Declared inside the registry file (binary CWB data — positional attribute files)  |
| Temp working dir      | `/tmp/ccc-*` (created per session by the `ccc` package)                            |

Accessed on demand for each KWIC/n-gram query; not preloaded into memory. See `api_swedeb/core/cwb/`.

### 5. Speech Text — Backend

One of two backends is active, controlled by `speech.storage_backend` in `config.yml`.

#### 5a. Legacy backend (`storage_backend: legacy`)

**Config**: `vrt.folder`

| Resource                                  | Notes                                                                          |
|-------------------------------------------|--------------------------------------------------------------------------------|
| `{vrt.folder}/{year}/{protocol_name}.zip` | Per-protocol ZIP files containing `metadata.json` + POS-tagged utterance JSON |

Accessed lazily per speech retrieval request. See `api_swedeb/legacy/load.py::ZipLoader`.

#### 5b. Prebuilt backend (`storage_backend: prebuilt`)

**Config**: `speech.bootstrap_corpus_folder`

| File                                                       | Notes                                                           |
|------------------------------------------------------------|-----------------------------------------------------------------|
| `{bootstrap_corpus_folder}/speech_lookup.feather`          | Speech-ID → (feather_file, row) index, loaded at startup        |
| `{bootstrap_corpus_folder}/{year}/{protocol_name}.feather` | Per-protocol speech tables, LRU-cached (default: 128 protocols) |

See `api_swedeb/core/speech_store.py::SpeechStore` and `api_swedeb/core/speech_repository_fast.py`.

### Summary

| Resource               | Format             | Config key                              | Load trigger                                  |
|------------------------|--------------------|-----------------------------------------|-----------------------------------------------|
| Speech index           | Feather / CSV.gz   | `dtm.folder` + `dtm.tag`               | App startup (lazy on first request)           |
| DTM / VectorizedCorpus | `.npz` + `.pickle` | `dtm.folder` + `dtm.tag`               | First word-trends or n-gram request           |
| Speech text (legacy)   | ZIP/JSON           | `vrt.folder`                            | Each speech retrieval request                 |
| Speech text (prebuilt) | Feather            | `speech.bootstrap_corpus_folder`        | Lookup index at startup; data files on demand |
| Metadata DB            | SQLite             | `metadata.filename`                     | App startup (lazy on first request)           |
| CWB corpus             | Binary CWB data    | `cwb.registry_dir` + `cwb.corpus_name` | Each KWIC/n-gram query                        |

### Appendix: Folder Inventory (`data/1867-2020/v1.4.1/`)

| Path (relative to `data/1867-2020/`)              | Description                           | API uses?               | Notes                                                   |
|---------------------------------------------------|---------------------------------------|-------------------------|---------------------------------------------------------|
| `cwb/`                                            | CWB binary corpus data                | **Yes**                 | Referenced by the registry file                         |
| `dtm/text/*`                                      | Speech index (CSV.gz / *.feather)     | **Yes**                 | Primary filter table; loaded at startup                 |
| `metadata/riksprot_metadata.v1.1.3.db`            | Metadata SQLite database              | **Yes**                 | Source of all PersonCodecs tables + `speaker_notes`     |
| `speeches/bootstrap_corpus/{year}/prot-*.feather` | Per-protocol speech tables            | **Yes** (prebuilt only) | LRU-cached on demand when `storage_backend: prebuilt`   |
| `speeches/bootstrap_corpus/speech_lookup.feather` | Speech-ID → feather location index    | **Yes** (prebuilt only) | Loaded at startup when `storage_backend: prebuilt`      |
| `tagged_frames/{year}/prot-*.zip`                 | ZIP archives of POS-tagged utterances | **Yes** (legacy only)   | Used when `storage_backend: legacy`; per-request, lazy  |
| `dehyphen/word-frequencies.pkl`                   | Word frequency table                  | No                      | Build-time dehyphenation only                           |
| `dtm/*.yml`                                       | Vectorization option files            | No                      | Build-time options, not read at runtime                 |
| `dtm/lemma/`                                      | DTM built on lemma tokens             | No                      | Config sets `dtm.tag=text`; lemma corpus not configured |
| `metadata/v1.1.3/*.csv`                           | Raw metadata CSV files                | No                      | Used to build the `.db`; not read at runtime            |
| `registry/riksprot_1867_2020_v141`                | CWB registry file                     | Indirectly              | Installed to `cwb.registry_dir` at deploy time          |
| `riksdagen-records/`                              | Source ParlaCLARIN XML                | No                      | Upstream source; not read by API                        |
| `speech-index.csv.gz`, `speech-index.feather`     | Top-level speech index copies         | No                      | Standalone exports; API loads from `dtm/text/`          |
| `speeches/bootstrap_corpus/speech_index.feather`  | Speech index inside bootstrap corpus  | No                      | Build artifact; API uses `dtm/text/` index instead      |
| `speeches/tagged_frames_speeches_lemma.feather/`  | Tagged speech feather dataset (lemma) | No                      | Build artifact                                          |
| `speeches/tagged_frames_speeches_text.feather/`   | Tagged speech feather dataset         | No                      | Build artifact                                          |
| `speeches/text_speeches_base.zip`                 | Plain text speeches ZIP               | No                      | Build artifact                                          |
| `speeches/text_speeches_dedent_dehyphen.zip`      | Dehyphenated speeches ZIP             | No                      | Build artifact                                          |
| `vrt/*.vrt.gz`                                    | VRT source files                      | No                      | Used to build the CWB corpus; not read at runtime       |

- `tagged_frames/config*.yml`, `version`, `metadata_version` are version/config marker files, not used (build artifacts)
- `Makefile`, `*.log`, `opts/`, `protocols.txt`, `tag.sh`, `.env` are build tooling and logs, not used (pipeline artefacts)
