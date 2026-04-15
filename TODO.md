
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

#  VS Code Codex extension

In the VS Code Codex extension, you can add file context in three main ways:

1. **Open the file**
   The IDE extension automatically includes your **open files** as context. ([OpenAI Utvecklare][1])

2. **Select code/text before prompting**
   The extension also automatically includes the **currently selected text range** in the editor. ([OpenAI Utvecklare][2])

3. **Tag the file in the prompt with `@`**
   You can explicitly reference a file by mentioning it in your prompt, for example:

   ```text
   Use @backend/app/services/validation_service.py as context and explain how validation flows through the backend.
   ```

   OpenAI’s IDE docs give examples like `@example.tsx` and `@resources.ts` in prompts. ([OpenAI Utvecklare][3])

A reliable workflow is:

* open the file you want Codex to use
* optionally highlight the exact function/class/block
* ask your question and tag the file with `@path/to/file`

Example:

```text
Review @src/normalizer.py and @src/link.py. Focus on the selected function and explain why FK resolution might fail here.
```

If you want faster access, the extension also exposes commands for **adding items to Codex context**, and you can bind those through the Codex chat settings → **Keyboard shortcuts** or VS Code keyboard shortcuts. ([OpenAI Utvecklare][4])

A few practical tips:

* Use `@file` when the file is important and must not be missed. ([OpenAI Utvecklare][3])
* Keep only relevant files open, since open files are included automatically. ([OpenAI Utvecklare][1])
* Select the exact code region when you want a very focused answer. ([OpenAI Utvecklare][2])

If you want, I can give you a set of example prompts for “explain this file”, “review this function”, and “modify these two files together” in Codex.

[1]: https://developers.openai.com/codex/workflows?utm_source=chatgpt.com "Workflows – Codex | OpenAI Developers"
[2]: https://developers.openai.com/codex/prompting?utm_source=chatgpt.com "Prompting – Codex | OpenAI Developers"
[3]: https://developers.openai.com/codex/ide/features?utm_source=chatgpt.com "Features – Codex IDE | OpenAI Developers"
[4]: https://developers.openai.com/codex/ide?utm_source=chatgpt.com "IDE extension – Codex | OpenAI Developers"

