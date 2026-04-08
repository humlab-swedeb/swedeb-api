# Quick Install Guide

## Overview

This guide provides quick instructions for installing and configuring Swedeb API application to test, ~~staging or~~, and production. 

## Prequisites

- The target branch (`main`, `staging` or `dev`) must be set up and functional with all tests passed.
- A valid configuration file `config.yaml` must available, adapted for the target environment.
- Access to the target environment (`test`, `staging`, `production`) with necessary permissions.
  - Root access (i.e. `sudo`) is required for installation and configuration.
- A `.env` file with setup and ready for the target environment.

## Target folder structure

The 
```
.
├── configuration
│   ├── image_builds                                                # NOT USED
│   ├── quadlets                                                    # Podman stuff
│   │   ├── swedeb-staging-app.container                            
│   │   └── swedeb-staging-app.network
│   └── secrets
│       └── config.yml                                              # Swedeb API runtime config
├── data
│   ├── metadata
│   │   ├── riksprot_metadata.v1.1.3.db                             # Sqlite metadata database
│   │   └── v1.1.3                                                  # Raw metadata files
│   │       ├── ...raw metadata files...
│   │       └── version 
│   └── v1.4.1
│       ├── dehyphen
│       │   └── word-frequencies.pkl                                # Deehyphen statistics
│       ├── dtm
│       │   ├── lemma                                               # DTM lemma
│       │   │   ├── lemma_document_index.csv.gz                     #   DTM document index
│       │   │   ├── lemma_document_index.feather                    #   DTM document (feather format)
│       │   │   ├── lemma_token2id.json.gz                          #   DTM dictionary
│       │   │   ├── lemma_vector_data.npz                           #   DTM SciPy sparse matrix
│       │   │   └── lemma_vectorizer_data.json                      #   DTM generation opts
│       │   └── text                                                # DTM text (same structure as lemma)
│       │       ├── (same set of data as for dtm lemma)
│       │       └── text_vectorizer_data.json
│       ├── registry                                                # CWB Workbench registry
│       │   ├── ...
│       │   └── riksprot_corpus                                     #   Corpus' entry name in CWB
│       ├── riksdagen-records                                       # Shallow copy of (included) corpus data
│       │   ├── ...Swerik XML records...
│       │   ├── prot-ak.xml
│       │   ├── prot-ek.xml
│       │   └── prot-fk.xml
│       ├── riksprot_metadata.v1.1.3.db                             # Sqlite metadata database (same as above)
│       ├── speeches
│       │   ├── tagged_frames_speeches_lemma.feather                # VRT Speech corpus (lemma)
│       │   │   ├── ...individual VRT files...                      #   VRT files (one file per record file)
│       │   │   ├── document_index.feather                          #   VRT document index 
│       │   │   └── token2id.feather
│       │   ├── tagged_frames_speeches_text.feather                 # VRT Speech corpus (non-lemmatized)
│       │   │   ├── (individual VRT files)                          #   VRT files (one file per record file)
│       │   │   ├── document_index.feather
│       │   │   └── token2id.feather
│       │   ├── text_speeches_base.zip                              # Speech text corpus (one file per speech)
│       │   └── text_speeches_dedent_dehyphen.zip                   # Speech text corpus (dedented and dehyphenated)
│       ├── speech-index.csv.gz                                     # Speech index
│       ├── speech-index.feather                                    #   Speech index (feather format)
│       └── tagged_frames                                           # Tagged corpus
│           ├── config_v1.4.1_v1.1.3.yml                            #   Tegging run time options
│           ├── (tagged frames data)                                #   One JSON file per protocol
│           ├── metadata_version                                    #   Metadata version used in tagging
│           └── version
├── logs                                                            # Logs folder 
├── staging
│   ├── .env                                                        # Container build & runtonme environment variables
│   ├── compose.yml                                                 # Container compose file
│   └── config.yml                                                  #   Swedeb API runtime config (check .env which config is used)
```

## Quick Install on Staging

| Config Element | Staging             | Production             | Test             |
| -------------- | ------------------- | ---------------------- | ---------------- |
| Deploy user    | swedeb_staging      | (swedeb_production)    | (swedeb_test)    |
| Deploy folder  | /srv/swedeb_staging | /srv/swedeb_production | /srv/swedeb_test |
| Trigger branch | staging             | main                   | (dev)            |
| Deploy tag     | staging             | latest                 |                  |
|                |                     |                        |                  |

1. Create a new PR from `dev` to trigger branch (e.g. `staging`). This triggers an automatic build using GitHub Actions and create the target container image on GHCR.

2. Verify that the new image is available on GHCR.
    1. Verify that the last GitHub Actions workflow run for the PR was successful.
    2. Verify that the new container image exists (e.g. `ghcr.io/humlab-swedeb/swedeb-api:staging`).
    3. You can also verify the that new image exists under "Packages" in the GitHub repository.
   
3. Log in to the staging server and enter the Quadlet shell for the deploy user and folder.
    1. Switch to root user using `sudo su -`.
    2. Change directory to the target environment (e.g. `cd /srv/swedeb_staging`).
    3. Switch to deploy user with `manage-quadlet shell`.
    See [How do I enter Quadlet shell?](../FAQ.md#how-do-i-enter-quadlet-shell) for instructions.

4. Ensure that you can rollback to the previous version in the target environment.
  - If needed, create a backup of the current `config.yaml` and `.env` files.
  - If needed, and relevant, verify the Git status of current deploy folder.
  - Ensure that the container images for current deploy are tagged appropriately for rollback.

5. Pull the latest container image from GHCR.
    ```bash
    podman image pull ghcr.io/humlab-swedeb/swedeb-api:"deploy-tag"
    ```

6. Updated configuration files (if needed).
  - Replace `config.yml` and `.env` under `configuration/secrets` with the new versions.

7. Reinstall the Quadlet to apply the new image and configuration.
    ```bash
    manage-quadlet remove
    manage-quadlet install
    ```

8. Verify that the application is running as expected.
  - Verify that container is running with `podman ps` (note the container ID).
  - Check the logs using `podman logs <container_id>`.
  - Test the application functionality to ensure everything is working correctly.
  
Replace `deploy-tag` with the appropriate tag for the target environment (e.g. `staging`, `latest`).
