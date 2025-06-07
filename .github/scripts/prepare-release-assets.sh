#!/bin/bash
set -e

# ==============================================================================
#  HELPER FUNCTIONS
# ==============================================================================

# Defines a function to check if a string is a valid SemVer 2.0.0.
# The regex is from https://semver.org/.
is_semver() {
  local version_string="$1"
  # Note: The C-style comment `/* ... */` is not valid in Bash. Use `#`.
  local SEMVER_REGEX="^(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)(\\-[0-9A-Za-z-]+(\\.[0-9A-Za-z-]+)*)?(\\+[0-9A-Za-z-]+(\\.[0-9A-Za-z-]+)*)?$"
  
  if [[ "$version_string" =~ $SEMVER_REGEX ]]; then
    return 0 # Success
  else
    return 1 # Failure
  fi
}

# Defines a function to synchronize the version in pyproject.toml and __init__.py.
sync_version() {
  local new_version="$1"
  local init_filename="api_swedeb/__init__.py" # Ensure this path is correct
  local version_line="__version__ = \"${new_version}\""

  echo "info: Updating version to ${new_version} in pyproject.toml..."
  poetry version "$new_version"

  echo "info: Synchronizing version in ${init_filename}..."
  if [ ! -f "$init_filename" ]; then
    echo "warning: File '${init_filename}' not found. Skipping synchronization."
    return 0 # Return success, as this may be intentional
  fi

  if grep -q -E "^__version__\s*=\s*.*" "$init_filename"; then
    # Line exists, update it
    sed -i -E "s/^__version__\s*=\s*.*/${version_line}/" "$init_filename"
  else
    # Line does not exist, append it
    echo -e "\n${version_line}" >> "$init_filename"
  fi

  echo "info: Successfully synchronized version in ${init_filename}."
}

# ==============================================================================
#  MAIN SCRIPT LOGIC
# =================================================_============================

if [ -z "$1" ]; then
  # Redirect error messages to stderr (>&2)
  echo "Usage: $0 <new_version>" >&2
  echo "Error: New version argument is missing." >&2
  echo "Example: $0 1.2.3" >&2
  exit 1
fi

VERSION=$1

if ! is_semver "$VERSION"; then
  echo "Usage: $0 <new_version>" >&2
  echo "Error: Provided version '${VERSION}' is not a valid Semantic Version." >&2
  echo "Please use the format Major.Minor.Patch (e.g., 1.2.3 or 0.9.1-alpha.1)." >&2
  exit 1
fi

echo "--- Preparing release assets for version ${VERSION} ---"

sync_version "$VERSION"

echo "info: Building Python wheel..."
poetry build

echo "info: Assets prepared successfully in dist/ directory."