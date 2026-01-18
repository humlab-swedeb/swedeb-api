# API Codebase Refactoring Plan: Focused Services Architecture

## Current State Analysis

### Problem Areas
```
api_swedeb/api/utils/corpus.py  (215 lines, 20+ methods)
├── Metadata queries (get_party_meta, get_gender_meta, etc.)
├── Speech operations (get_speech, get_speaker, get_anforanden)
├── Word/vocabulary operations (word_in_vocabulary, get_word_hits, get_word_trends)
├── Speaker filtering (_get_filtered_speakers, get_speakers)
└── Caching via Lazy() and cached_property

api_swedeb/api/dependencies.py
├── Global singleton __shared_corpus
├── get_cwb_corpus() for CWB integration
└── Sparse dependency injection

api_swedeb/api/utils/
├── kwic.py, ngrams.py, speech.py, word_trends.py
├── Each imports corpus and calls multiple methods
└── No clear ownership/responsibility
```

### Current Test Structure
```
tests/api_swedeb/api/utils/
├── test_corpus.py (tests Corpus class)
├── test_kwic.py, test_ngrams.py, test_speech.py (test utility functions)
└── test_word_trends.py

tests/integration/
├── test_tool_router.py (routes using Corpus)
└── test_metadata_router.py
```

### Dependencies Flow
```
Routes → utils/{kwic,ngrams,speech,word_trends}.py → corpus.py → core/*
```

---

## Target Architecture

```
api_swedeb/api/services/
├── __init__.py
├── corpus_loader.py         # CorpusLoader - manages expensive I/O
├── metadata_service.py      # MetadataService - metadata queries
├── speech_service.py        # SpeechService - speech operations
├── word_service.py          # WordService - vocabulary & trends
├── speaker_service.py       # SpeakerService - speaker queries
└── corpus_facade.py         # CorpusFacade (optional, coordinates services)

api_swedeb/api/dependencies.py  (enhanced)
├── Proper DI for each service
├── Caching at CorpusLoader level
└── Service factory functions

api_swedeb/api/utils/  (refactored)
├── kwic.py, ngrams.py, speech.py (call services, not corpus)
└── No direct corpus dependency

tests/api_swedeb/api/services/  (NEW)
├── test_corpus_loader.py
├── test_metadata_service.py
├── test_speech_service.py
├── test_word_service.py
├── test_speaker_service.py
└── test_corpus_facade.py (if used)
```

---

## Refactoring Phases (Incremental)

### Phase 0: Setup & Infrastructure (No functional changes)
**Goal**: Prepare structure for refactoring without changing behavior

**Steps**:
1. Create `api_swedeb/api/services/` directory
2. Create `test/api_swedeb/api/services/` directory
3. Create empty service files with docstrings
4. Move cache/dependency logic to separate `cache_manager.py`

**Tests to Pass**:
- All existing tests in `tests/api_swedeb/api/utils/` pass unchanged
- All existing integration tests pass unchanged

**Time**: ~30 min | **Risk**: Low

**Commit**: "refactor: create services directory structure"

---

### Phase 1: Extract CorpusLoader Service
**Goal**: Extract corpus initialization and caching from Corpus class

**Current**:
```python
# corpus.py
class Corpus:
    def __init__(self):
        self.__vectorized_corpus = Lazy(lambda: load_dtm_corpus(...))
        self.__lazy_person_codecs = Lazy(lambda: md.PersonCodecs().load(...))
        self.__lazy_document_index = Lazy(lambda: load_speech_index(...))
```

**Target**:
```python
# services/corpus_loader.py
class CorpusLoader:
    """Manages loading and caching of corpus data"""
    def __init__(self, dtm_tag: str, dtm_folder: str, metadata_filename: str):
        ...
    
    @property
    def vectorized_corpus(self) -> IVectorizedCorpus:
        ...
    
    @property
    def person_codecs(self) -> PersonCodecs:
        ...
    
    @property
    def document_index(self) -> pd.DataFrame:
        ...

# dependencies.py
def get_corpus_loader() -> CorpusLoader:
    global __loader
    if __loader is None:
        __loader = CorpusLoader(...)
    return __loader
```

**Files Modified**:
- ✅ Create: `api_swedeb/api/services/corpus_loader.py`
- ✅ Create: `tests/api_swedeb/api/services/test_corpus_loader.py`
- 🔄 Modify: `api_swedeb/api/dependencies.py` (new getter function)
- 🔄 Modify: `api_swedeb/api/utils/corpus.py` (use CorpusLoader internally)
- 🔄 Update: `tests/api_swedeb/api/utils/test_corpus.py` (mock CorpusLoader)

**Tests to Pass**:
- `tests/api_swedeb/api/services/test_corpus_loader.py` - new tests for CorpusLoader
- `tests/api_swedeb/api/utils/test_corpus.py` - all existing Corpus tests pass
- All integration tests pass

**Time**: ~1 hour | **Risk**: Low

**Commit**: "refactor: extract CorpusLoader service"

---

### Phase 2: Extract MetadataService
**Goal**: Extract all metadata-related queries into focused service

**Current** (in Corpus):
```python
def get_party_meta(self) -> pd.DataFrame:
def get_gender_meta(self):
def get_chamber_meta(self):
def get_office_type_meta(self):
def get_sub_office_type_meta(self):
```

**Target**:
```python
# services/metadata_service.py
class MetadataService:
    """Handle metadata queries"""
    def __init__(self, loader: CorpusLoader):
        self.loader = loader
    
    def get_party_meta(self) -> pd.DataFrame:
        return self.loader.person_codecs.party.sort_values(...)
    
    def get_gender_meta(self) -> pd.DataFrame:
        ...
    # ... etc
```

**Files Modified**:
- ✅ Create: `api_swedeb/api/services/metadata_service.py`
- ✅ Create: `tests/api_swedeb/api/services/test_metadata_service.py`
- 🔄 Modify: `api_swedeb/api/dependencies.py` (add get_metadata_service)
- 🔄 Modify: `api_swedeb/api/utils/corpus.py` (delegate to MetadataService)
- 🔄 Modify: `api_swedeb/api/utils/metadata.py` (update to use MetadataService)
- 🔄 Update: `tests/api_swedeb/api/utils/test_corpus.py` (remove metadata test cases, redirect to metadata_service tests)

**Routes Impacted**:
- `tool_router.py`: routes calling `corpus.get_party_meta()` → `metadata_svc.get_party_meta()`
- `metadata_router.py`: update Depends injection

**Tests to Pass**:
- `tests/api_swedeb/api/services/test_metadata_service.py` - new
- `tests/api_swedeb/api/utils/test_corpus.py` - metadata tests removed
- `tests/integration/test_metadata_router.py` - all pass
- All other integration tests pass

**Time**: ~1.5 hours | **Risk**: Medium (touches metadata_router)

**Commit**: "refactor: extract MetadataService"

---

### Phase 3: Extract SpeechService
**Goal**: Extract speech-related operations

**Current** (in Corpus):
```python
def get_speech(self, document_name: str) -> Speech:
def get_speaker(self, document_name: str) -> str:
def get_anforanden(self, selections: dict) -> pd.DataFrame:
```

**Target**:
```python
# services/speech_service.py
class SpeechService:
    def __init__(self, loader: CorpusLoader):
        self.loader = loader
    
    def get_speech(self, document_name: str) -> Speech:
        return self.loader.repository.speech(speech_name=document_name)
    
    def get_speaker(self, document_name: str) -> str:
        ...
    
    def get_anforanden(self, selections: dict) -> pd.DataFrame:
        speeches = get_speeches_by_opts(self.loader.document_index, selections)
        ...
```

**Files Modified**:
- ✅ Create: `api_swedeb/api/services/speech_service.py`
- ✅ Create: `tests/api_swedeb/api/services/test_speech_service.py`
- 🔄 Modify: `api_swedeb/api/dependencies.py` (add get_speech_service)
- 🔄 Modify: `api_swedeb/api/utils/corpus.py` (delegate to SpeechService)
- 🔄 Modify: `api_swedeb/api/utils/speech.py` (update to use SpeechService)
- 🔄 Update: `tests/api_swedeb/api/utils/test_corpus.py` (remove speech tests)

**Routes Impacted**:
- `tool_router.py`: routes calling `corpus.get_speech()` → `speech_svc.get_speech()`
- Integration tests using speech endpoints

**Tests to Pass**:
- `tests/api_swedeb/api/services/test_speech_service.py` - new
- `tests/api_swedeb/api/utils/test_corpus.py` - speech tests removed
- `tests/integration/test_tool_router.py` - speech endpoints pass
- All other integration tests pass

**Time**: ~1.5 hours | **Risk**: Medium (touches tool_router speech endpoints)

**Commit**: "refactor: extract SpeechService"

---

### Phase 4: Extract WordService
**Goal**: Extract vocabulary and word trends operations

**Current** (in Corpus):
```python
def word_in_vocabulary(self, word):
def filter_search_terms(self, search_terms):
def get_word_trend_results(self, search_terms, filter_opts, normalize):
def get_anforanden_for_word_trends(self, selected_terms, filter_opts):
def get_word_hits(self, search_term, n_hits):
```

**Target**:
```python
# services/word_service.py
class WordService:
    def __init__(self, loader: CorpusLoader):
        self.loader = loader
    
    def word_in_vocabulary(self, word: str) -> str | None:
        ...
    
    def filter_search_terms(self, search_terms: list[str]) -> list[str]:
        ...
    
    def get_word_trend_results(self, search_terms, filter_opts, normalize):
        ...
    
    def get_word_hits(self, search_term, n_hits):
        ...
```

**Files Modified**:
- ✅ Create: `api_swedeb/api/services/word_service.py`
- ✅ Create: `tests/api_swedeb/api/services/test_word_service.py`
- 🔄 Modify: `api_swedeb/api/dependencies.py` (add get_word_service)
- 🔄 Modify: `api_swedeb/api/utils/corpus.py` (delegate to WordService)
- 🔄 Modify: `api_swedeb/api/utils/word_trends.py` (update to use WordService)
- 🔄 Modify: `api_swedeb/api/utils/ngrams.py` (update to use WordService)
- 🔄 Update: `tests/api_swedeb/api/utils/test_corpus.py` (remove word tests)

**Routes Impacted**:
- `tool_router.py`: word trend endpoints
- Integration tests for word trends and ngrams

**Tests to Pass**:
- `tests/api_swedeb/api/services/test_word_service.py` - new
- `tests/api_swedeb/api/utils/test_corpus.py` - word tests removed
- `tests/api_swedeb/api/utils/test_word_trends.py` - all pass with new WordService
- `tests/api_swedeb/api/utils/test_ngrams.py` - all pass with new WordService
- `tests/integration/test_tool_router.py` - word trend endpoints pass
- All other integration tests pass

**Time**: ~2 hours | **Risk**: Medium-High (affects word trends endpoints)

**Commit**: "refactor: extract WordService"

---

### Phase 5: Extract SpeakerService
**Goal**: Extract speaker-related queries and filtering

**Current** (in Corpus):
```python
def _get_filtered_speakers(self, selection_dict, df):
def get_speakers(self, selections):
def get_years_start(self) -> int:
def get_years_end(self) -> int:
```

**Target**:
```python
# services/speaker_service.py
class SpeakerService:
    def __init__(self, loader: CorpusLoader, word_service: WordService):
        self.loader = loader
        self.word_service = word_service
    
    def _get_filtered_speakers(self, selection_dict, df):
        ...
    
    def get_speakers(self, selections: dict) -> pd.DataFrame:
        ...
    
    def get_years_range(self) -> tuple[int, int]:
        """Returns (start_year, end_year)"""
        ...
```

**Files Modified**:
- ✅ Create: `api_swedeb/api/services/speaker_service.py`
- ✅ Create: `tests/api_swedeb/api/services/test_speaker_service.py`
- 🔄 Modify: `api_swedeb/api/dependencies.py` (add get_speaker_service)
- 🔄 Modify: `api_swedeb/api/utils/corpus.py` (delegate to SpeakerService)
- 🔄 Modify: `api_swedeb/api/utils/metadata.py` (update to use SpeakerService)
- 🔄 Update: `tests/api_swedeb/api/utils/test_corpus.py` (remove speaker tests)

**Routes Impacted**:
- `metadata_router.py`: speaker endpoints

**Tests to Pass**:
- `tests/api_swedeb/api/services/test_speaker_service.py` - new
- `tests/api_swedeb/api/utils/test_corpus.py` - speaker tests removed
- `tests/integration/test_metadata_router.py` - speaker endpoints pass
- All integration tests pass

**Time**: ~1.5 hours | **Risk**: Medium

**Commit**: "refactor: extract SpeakerService"

---

### Phase 6: Create CorpusFacade (Optional Coordination Layer)
**Goal**: Optional - Provide single unified service if needed for coordination

**Target**:
```python
# services/corpus_facade.py
class CorpusFacade:
    """Facade coordinating all corpus services"""
    def __init__(
        self,
        loader: CorpusLoader,
        metadata: MetadataService,
        speech: SpeechService,
        word: WordService,
        speaker: SpeakerService,
    ):
        self.loader = loader
        self.metadata = metadata
        self.speech = speech
        self.word = word
        self.speaker = speaker
    
    # Optional: delegate methods that appear frequently
    def get_party_meta(self):
        return self.metadata.get_party_meta()
    
    # Or: provide convenient combined operations
    def get_speech_with_speaker(self, doc_name):
        speech = self.speech.get_speech(doc_name)
        speaker = self.speech.get_speaker(doc_name)
        return (speech, speaker)
```

**Rationale**: Only create if routes would benefit from single dependency
- Consider skipping if routes are happy with injecting specific services

**Files Modified**:
- ✅ Create: `api_swedeb/api/services/corpus_facade.py`
- ✅ Create: `tests/api_swedeb/api/services/test_corpus_facade.py`
- 🔄 Modify: `api_swedeb/api/dependencies.py` (add get_corpus_facade)

**Tests to Pass**:
- All previous service tests still pass
- `tests/api_swedeb/api/services/test_corpus_facade.py` - new
- All integration tests pass unchanged (if not using facade yet)

**Time**: ~45 min | **Risk**: Low (coordinating layer, no behavior change)

**Commit**: "refactor: create optional CorpusFacade coordination layer"

---

### Phase 7: Update Routes to Use Services (Optional)
**Goal**: Gradually update routes to use services directly instead of facade/corpus

**Approach**: Incremental by router
1. Update `metadata_router.py` to inject services
2. Update `tool_router.py` to inject services
3. Remove or deprecate old `Corpus` class usage

**For Each Router**:
- Before: `corpus: Corpus = Depends(get_shared_corpus)`
- After: 
  ```python
  metadata_svc: MetadataService = Depends(get_metadata_service),
  speech_svc: SpeechService = Depends(get_speech_service),
  ```

**Tests**:
- All integration tests for that router pass with new injections
- No behavior change

**Time**: ~1 hour per router | **Risk**: Medium (changes route signatures)

**Commit**: "refactor: update {router_name} to use focused services"

---

### Phase 8: Cleanup & Deprecation (Final Step)
**Goal**: Remove old Corpus class or deprecate gracefully

**Options**:
1. **Full Removal**: Delete Corpus class, update any remaining imports
2. **Deprecation Path**: Keep Corpus as thin wrapper over services (backwards compatible)

**Decision Needed**:
- Do we need backwards compatibility with existing Corpus usage?
- Or clean break with Phases 1-7?

**Files Modified**:
- 🔄 Modify: `api_swedeb/api/utils/corpus.py` (either delete or thin wrapper)
- 🔄 Modify: `api_swedeb/api/dependencies.py` (remove get_shared_corpus or deprecate)
- 🗑️ Delete: `tests/api_swedeb/api/utils/test_corpus.py` (if Corpus removed)

**Tests to Pass**:
- All service tests still pass
- All integration tests still pass

**Time**: ~30 min | **Risk**: Low (final cleanup)

**Commit**: "refactor: remove/deprecate old Corpus class"

---

## Test File Structure After Refactoring

### Before
```
tests/api_swedeb/api/utils/
├── test_corpus.py              # 215+ lines, all methods mixed
├── test_kwic.py
├── test_ngrams.py
├── test_speech.py
└── test_word_trends.py
```

### After
```
tests/api_swedeb/api/services/     # NEW: organized by service
├── test_corpus_loader.py           # Caching, lazy loading
├── test_metadata_service.py        # Metadata queries
├── test_speech_service.py          # Speech operations
├── test_word_service.py            # Vocabulary & trends
├── test_speaker_service.py         # Speaker filtering
└── test_corpus_facade.py           # (Optional) Coordination

tests/api_swedeb/api/utils/         # Simplified
├── test_kwic.py                    # Functions using services
├── test_ngrams.py
├── test_speech.py
└── test_word_trends.py

tests/integration/                  # Routes - unchanged structure
├── test_tool_router.py
├── test_metadata_router.py
└── ...

tests/api_swedeb/core/             # Core logic - unchanged
├── test_codecs.py
├── test_speech_index.py
└── ...
```

---

## Risk & Mitigation

| Phase | Risk Level | Mitigation |
|-------|-----------|-----------|
| 0 | Low | Just structure, no changes |
| 1 | Low | Corpus still wraps CorpusLoader internally |
| 2 | Medium | Metadata router uses both Corpus & MetadataService temporarily |
| 3 | Medium | Speech endpoints use both for a phase |
| 4 | Medium-High | Word trends is complex, test heavily |
| 5 | Medium | Speaker filtering has complex logic |
| 6 | Low | Optional layer, additive only |
| 7 | Medium | Route signature changes, but DI handles it |
| 8 | Low | Cleanup, tested by previous phases |

---

## Success Criteria

✅ **After Each Phase**:
- All existing tests pass
- New service has dedicated test file
- Test structure mirrors service structure
- No behavior changes (refactoring only)
- Integration tests fully pass

✅ **After All Phases**:
- Single Responsibility Principle: each service has one reason to change
- Testability: services are independently testable
- Dependency Clarity: routes show dependencies explicitly
- Code Organization: logical file/folder structure
- Coverage: no loss of test coverage
- Performance: no regression (caching still works)

---

## Timeline Estimate

| Phase | Time | Cumulative |
|-------|------|-----------|
| 0: Setup | 30 min | 30 min |
| 1: CorpusLoader | 1 hour | 1.5 hours |
| 2: MetadataService | 1.5 hours | 3 hours |
| 3: SpeechService | 1.5 hours | 4.5 hours |
| 4: WordService | 2 hours | 6.5 hours |
| 5: SpeakerService | 1.5 hours | 8 hours |
| 6: Facade (opt) | 45 min | 8.75 hours |
| 7: Update Routes | 1-2 hours | 10 hours |
| 8: Cleanup | 30 min | 10.5 hours |

**Total**: ~10-11 hours (1-2 development days)

---

## Next Steps

1. **Review & Approve Plan**: Confirm this approach aligns with goals
2. **Phase 0 Implementation**: Start infrastructure setup
3. **Phase 1**: Extract CorpusLoader with full test coverage
4. **Iterate**: One phase per PR/commit, steady progress

**Proceed? Any adjustments to the plan?**
