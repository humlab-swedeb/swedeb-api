# Quick Install Guide

## Overview

This guide provides quick instructions for installing and configuring branch /dev of the Swedeb API application to test, staging or production. 

## Prequisites

- The branch `dev` must be set up and functional with all tests passed.
- A configuration file `config.yaml` available, adapted for the target environment.
- Access to the target environment (test, staging, production) with necessary permissions.
  -  Root access (i.e. sudo) is required for installation and configuration.
- A `.env` file with setup and ready for the target environment.

## Steps to Install on Staging

| Config Element | Staging             | Production             | Test             |
| -------------- | ------------------- | ---------------------- | ---------------- |
| Deploy user    | swedeb_staging      | (swedeb_production)    | (swedeb_test)    |
| Deploy folder  | /srv/swedeb_staging | /srv/swedeb_production | /srv/swedeb_test |
| Trigger branch | staging             | main                   | (dev)            |
| Deploy tag     | staging             | latest                 |                  |
|                |                     |                        |                  |

1. Create a new PR from `dev` to trigger branch (e.g. `staging`). This will trigger an automatic build using GitHub Actions and create the target container image on GHCR.
2. Verify that the new container image is available on GHCR.
    1. Verify that the last GitHub Actions workflow run for the PR was successful.
    2. Verify that the new container image is (e.g. `ghcr.io/humlab-swedeb/swedeb-api:staging`).
    3. You can also verify the that new imaghe exists under "Packages" in the GitHub repository.
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
