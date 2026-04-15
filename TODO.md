
 - [ ] TODO: Add config value for max_cached_protocols in SpeechStore
 - [ ] TODO: Improve design documentation 
 - [ ] TODO: Extract relevant design documentation from docs/MERGED_SPEECH_CORPUS_* to docs/DESIGN.md
 - [ ] TODO: Move prebuilt_speech_index to pyriksprot
 - [ ] TODO: Replace use of Codecs with prebuilt_speech_index
 - [ ] FIXME: Add strict mode to alignment check in CorpusLoader
 - [ ] TODO: fixa get_config_store i Shape Shifter att följa samma mönster som i detta project (enklare unit testing)
 - [ ] FIXME: Try using category type for names?

 - [ ] TODO: Go through _get_filtered_speakers and decide if it can be improved (e.g. using prebuilt index)
 - [ ] TODO: replace _get_filtered_speakers with get_filtered_speakers_improved
 - [ ] TODO: Use prebuilt speech index in these methods
  
| Current use                                    | File                                             | Replaceable? | Notes                                    |
|------------------------------------------------|--------------------------------------------------|--------------|------------------------------------------|
| `decode_speech_index()` on KWIC results        | `core/kwic/simple.py`                            | ✅ Done       | Migrated in #253                       |
| `decode_speech_index()` on search results      | `SearchService.get_speeches`                     | ✅ Yes        | Join on `speech_id`                      |
| `decode_speech_index()` on word-trend speeches | `WordTrendsService.get_speeches_for_word_trends` | ✅ Yes        | Same join                                |
| `person_codecs[person_id]` for speaker name    | `SearchService.get_speaker`                      | ✅ Yes        | Lookup in prebuilt index by `speaker_id` |

For all of these, the result is the same: replace a runtime codec translate-step with a
`DataFrame.join(prebuilt_speech_index, on='speech_id', how='left')`.

prot-YYYY-ABC-NNN
prot-YYYY-ABC-XK--NNN
prot-YYYY-ABC-XK--NNN-ZZ
prot-YYYY--NNN
prot-YYYY--XK--MMDD
prot-YYYY--XK--NNN
prot-YYYY--XK--NNN-ZZ
prot-YYYYYY--NNN

