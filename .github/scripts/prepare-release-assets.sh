#!/bin/bash
set -ex

VERSION=$1
if [ -z "$VERSION" ]; then
  echo "Version argument is missing!"
  exit 1
fi

echo "Preparing assets for version ${VERSION}..."

pipx install poetry
pipx install bump-my-version

bump-my-version bump --new-version "$VERSION" --allow-dirty --ignore-missing-files --list part
poetry build

echo "Assets prepared in dist/ directory."
