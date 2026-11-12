#!/usr/bin/env bash
# Report broken relative Markdown links in the given files.
#
# Usage: check_relative_links.sh <file> [<file>...]
#
# Resolves each "](target)" link against the file's own directory, matching the
# repository checker in scripts/check_doc_links.sh. Skips fragments, absolute
# paths, and external schemes. Exits non-zero when any link is broken.

set -euo pipefail

if [[ $# -eq 0 ]]; then
    printf 'usage: check_relative_links.sh <file> [<file>...]\n' >&2
    exit 2
fi

failed=0

# Print the lines of a file that are not inside a fenced code block. Markdown
# treats fenced content as opaque, so link syntax shown as an example inside a
# fence is documentation, not a link. Mirrors the handling in
# scripts/check_doc_links.sh.
strip_fenced_blocks() {
    awk '
        {
            line = $0
            sub(/^ {0,3}/, "", line)
            if (line ~ /^(`{3,}|~{3,})/) {
                ch = substr(line, 1, 1)
                len = 0
                while (substr(line, len + 1, 1) == ch) {
                    len++
                }
                if (!in_fence) {
                    in_fence = 1
                    fence_char = ch
                    fence_len = len
                    next
                }
                if (ch == fence_char && len >= fence_len) {
                    in_fence = 0
                    next
                }
            }
            if (!in_fence) {
                print
            }
        }
    ' "$1"
}

for document in "$@"; do
    if [[ ! -f "$document" ]]; then
        printf 'Missing file: %s\n' "$document" >&2
        failed=1
        continue
    fi

    document_dir="$(dirname "$document")"

    while IFS= read -r link; do
        [[ -n "$link" ]] || continue

        case "$link" in
            \#*|http://*|https://*|mailto:*|/*) continue ;;
        esac

        target="${link%%\?*}"
        target="${target%%\#*}"
        [[ -n "$target" ]] || continue

        if [[ ! -e "$document_dir/$target" ]]; then
            printf 'Broken link: %s -> %s\n' "$document" "$link" >&2
            failed=1
        fi
    done < <(strip_fenced_blocks "$document" | perl -ne 'while (/\]\(([^)]+)\)/g) { print "$1\n"; }')
done

if [[ "$failed" -ne 0 ]]; then
    exit 1
fi

printf 'Relative links are valid.\n'
