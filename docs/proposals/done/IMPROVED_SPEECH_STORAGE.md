# Proposal: Create merged speech JSON corpus

# Summary

The tagging workflow of the parliamentary corpus produces a JSON file such as ./prot-1867--ak--0118.json for each individual protocol (which is stored a ParlaCLARIN XML files). The JSON and associated metadata is stored in a ZIP file, one ZIP for each protocol. The ZIP has content such as this:

```
 λ unzip -l data/v1.4.1/tagged_frames/1867/prot-1867--ak--0118.zip
Archive:  data/v1.4.1/tagged_frames/1867/prot-1867--ak--0118.zip
  Length      Date    Time    Name
---------  ---------- -----   ----
      123  05-24-2025 17:00   metadata.json
   163769  05-24-2025 17:00   prot-1867--ak--0118.json
---------                     -------
   163892                     2 files
```

The JSON file contains a list of utterance with these keys:

| key             | description                   | example                                                 | type      |
|-----------------|-------------------------------|---------------------------------------------------------|---------- |
| u_id            | Utterance ID                  | "i-Cxjev5ciwFENrErGLaYTJj"                              | UUID      |
| who             | Speaker's ID                  | "i-6i387mH6JJaFpEkVcQ6eNv"                              | UUID or unknown |
| prev_id         | Pointer to previous utterance | null                                                    | UUID or null |
| next_id         | Pointer to NEXT utterance     | "i-6ZDUdPEePXpZVTt7DGC9ng"                              | UUID or null |
| paragraphs      | Text paragraphs in utterance  | [ "first paragraph", "second paragraph" ]               | list[str] |
| annotation      | PoS tagged (VRT), TSV         | "token\tlemma\tpos\txpos\n\u00bb\tvara\tVB\tVB.AN\n..." | str       |
| page_number     | Page number for utterance     | 2                                                       | int       |
| speaker_note_id | Speaker introduction/header   | "i-KDWC1bZThjvSLkhCxhYpC4"                              | UUID      |
| num_tokens      | Number of tokens in utterance | 11                                                      | int       |
| num_words       | Number of words in utterance  | 11                                                      | int       |

 such as this example:

```
[
    {
        "u_id": "i-Cxjev5ciwFENrErGLaYTJj",
        "who": "i-6i387mH6JJaFpEkVcQ6eNv",
        "prev_id": null,
        "next_id": "i-6ZDUdPEePXpZVTt7DGC9ng",
        "paragraphs": [
            "\u00bbUnder \u00e5beropande av vad s\u00e5lunda anf\u00f6rts f\u00e5r utskottet hemst\u00e4lla,"
        ],
        "annotation": "token\tlemma\tpos\txpos\n\u00bb\tvara\tVB\tVB.AN\nUnder\tunder\tPP\tPP\n\u00e5beropande\t\u00e5beropande\tNN\tNN.NEU.SIN.IND.NOM\nav\tav\tPP\tPP\nvad\tvad\tHP\tHP.NEU.SIN.IND\ns\u00e5lunda\ts\u00e5lunda\tAB\tAB\nanf\u00f6rts\tanf\u00f6ra\tVB\tVB.SUP.SFO\nf\u00e5r\tf\u00e5\tVB\tVB.PRS.AKT\nutskottet\tutskott\tNN\tNN.NEU.SIN.DEF.NOM\nhemst\u00e4lla\themst\u00e4lla\tVB\tVB.INF.AKT\n,\t,\tMID\tMID",
        "page_number": 2,
        "speaker_note_id": "missing",
        "num_tokens": 11,
        "num_words": 11
    },
    {
        "u_id": "i-6ZDUdPEePXpZVTt7DGC9ng",
        "who": "i-6i387mH6JJaFpEkVcQ6eNv",
        "prev_id": "i-Cxjev5ciwFENrErGLaYTJj",
        "next_id": "i-4jhe73cU4bGF9KWYdTw14i",
        "paragraphs": [
            "\u00bbVad betr\u00e4ffar de mera kvalificerade v\u00e4rntj\u00e4nst\u00f6vningarna, vilka...truncated...."
        ],
        "annotation": "token\tlemma\tpos\txpos\n\u00bb\t\u00bb\tMID\tMID\nVad\tvad\tHP\tHP.NEU.SIN.IND\nbetr\u00e4ffar\tbetr\u00e4ffa\tVB\tVB.PRS.AKT\nde\tden\tDT\tDT.UTR+NEU.PLU.DEF\nmera\tmycket\tAB\tAB.KOM\nkvalificerade\tkvalificerad\tPC\tPC.PRF.UTR+NEU.PLU.IND+DEF.NOM\nv\u00e4rntj\u00e4nst\u00f6vningarna\tv\u00e4rntj\u00e4nst\u00f6vning\tNN\tNN.UTR.PLU.DEF.NOM\n,\t,\tMID\tMID...truncated...",
        "page_number": 2,
        "speaker_note_id": "missing",
        "num_tokens": 77,
        "num_words": 77
    },
    {
        "u_id": "i-4jhe73cU4bGF9KWYdTw14i",
        "who": "i-6i387mH6JJaFpEkVcQ6eNv",
        "prev_id": "i-6ZDUdPEePXpZVTt7DGC9ng",
        "next_id": "i-QMNM9GevTZjU2bsqCtER2j",
        "paragraphs": [
            "text continues..."
        ],
        "annotation": "token\tlemma\tpos\txpos\n...truncated...",
        "page_number": 3,
        "speaker_note_id": "missing",
        "num_tokens": 241,
        "num_words": 241
    },
    {
        "u_id": "i-QMNM9GevTZjU2bsqCtER2j",
        "who": "i-6i387mH6JJaFpEkVcQ6eNv",
        "prev_id": "i-4jhe73cU4bGF9KWYdTw14i",
        "next_id": null,
        "paragraphs": [
            "paragraph text 1"
        ],
        "annotation": "token\tlemma\tpos\txpos\n...truncated...",
        "page_number": 3,
        "speaker_note_id": "missing",
        "num_tokens": 101,
        "num_words": 101
    },
    ...
]
```

Currently a speech is reconstructed from this source. A speech starts when the previous reference (prev_id) is null and end when next reference (next_id) is null. A speech is reconstructed by following the "prev/next" references associated to each utterance. Since the uttarances are in sorted order, the algorithm only need to consider if previous or next reference is null a non-null next_id should always point to previous utterance's "u_id".

I think storing the annotaded utterances in a ZIP like this is OK, but it's not optimal for fast consumption by Swedeb API. The number of speeches is > 1000000 so the process is slow when we for instance want to download a larget set of speeches.

I need a faster, pre-built speech structure, from which the speech repository can do fast lookups of data related to a speech. Ultimatly this structure should return "Speech" objects as created in "SpeechRepository".

The data is version controlled, so the produced "Speech" bject is predetermined by the current Corpus version and Metadata version.

The first thing to do is to create a "speech" level version of the JSON data i.e. producing speeches such as this:


|  key               | description                                                  | type            |
| ------------------ | ------------------------------------------------------------ |---------------- |
| speech_id          | Speech ID - the u_id of the first utterance                  | UUID            |
| speaker_id         | Speaker's ID as specified in `who` on first utterance        | UUID or unknown |
| speech_text        | Concatenated text of all utterances                          | list[str]       |
| annotation         | Concatenated annotations (header only from first uttarance)  | str             |
| page_number_start  | Page number for first utterance                              | int             |
| page_number_end    | Page number for first utterance                              | int             |
| speaker_note_id    | Speaker introduction/header                                  | UUID            |
| num_tokens         | Total number of tokens in utterance                          | int             |
| num_words          | Total number of words in utterance                           | int             |

We then, as is done in " in "SpeechRepository", we need to attach speaker-related information to each speech.

Please suggest a performant structure for this data. The system currently has no databas backend. I would in an
inital version like to keep the "SpeechRepository" interface as is to minimize major changes.

This is a FastAPI application, and a structure which is loaded and bhootstrapped at system startup is OK.

I can see the need of these capabilities:
 1. Capability to merge a single protocol's utterances into speeches as defined in table above.
 2. Capability to read all protocols zipped utterance files, convert each file to a merged speech file using (1), and store that file in an apropriate format.
 3. Capability to add speaker metadata to speeches from (2) as is done in "TextRepository".
 4. Store the overloaded data in an appropriate format
 5. Capability to bootstrap a structure with performant "Speech" instance retrieval

The demarcations between capabilities 3, 4 and 5 is a bit fuzzy related to what is actually stored on disk, what is done at system startup and what is done when actually retrieving a speech. It is also related to caching of data. It is also related to limitations of FastAPI/uvicorn, and capability of sharing data between workers.

Please analyse this and give me suggestions on how to solve this problem.
