#!/bin/bash
#c --party-file parties.tsv \

g_from_year=1867
g_to_year=1876

uv run generate-speech-archive \
    --from-year $g_from_year --to-year $g_to_year \
        -o archives/speeches_${g_from_year}.zip

for year_from in 1867 1920 1970; do
  uv run generate-speech-archive \
    --from-year $year_from --to-year $((year_from + 9)) \
    -o archives/speeches_${year_from}.zip
done
