"""Integration tests: verify speech_id alignment across all three corpus indexes."""

import pandas as pd


def test_index_diffs():
    """Verify that speech_id sets are identical across the tagged-speeches feather index,
    the DTM document index, and the prebuilt bootstrap_corpus speech_lookup.feather."""

    vrt_index_filename = "data/v1.4.1/speeches/tagged_frames_speeches_text.feather/document_index.feather"
    df_vrt: pd.DataFrame = pd.read_feather(vrt_index_filename, dtype_backend="pyarrow")

    dtm_index_filename = "data/v1.4.1/dtm/text/text_document_index.feather"
    df_dtm: pd.DataFrame = pd.read_feather(dtm_index_filename, dtype_backend="pyarrow")

    prebuilt_lookup_filename = "data/v1.4.1/speeches/bootstrap_corpus/speech_lookup.feather"
    df_prebuilt: pd.DataFrame = pd.read_feather(prebuilt_lookup_filename, dtype_backend="pyarrow")

    assert not df_dtm.empty, "Document index from DTM corpus is empty"
    assert not df_prebuilt.empty, "speech_lookup.feather from bootstrap_corpus is empty"

    # VRT (u_id) vs DTM (u_id)
    in_dtm_not_vrt = df_dtm[~df_dtm.u_id.isin(df_vrt.u_id)]
    in_vrt_not_dtm = df_vrt[~df_vrt.u_id.isin(df_dtm.u_id)]
    assert in_dtm_not_vrt.empty, f"DTM has {len(in_dtm_not_vrt)} speech_ids not in VRT index"
    assert in_vrt_not_dtm.empty, f"VRT index has {len(in_vrt_not_dtm)} speech_ids not in DTM"

    # DTM (u_id) vs prebuilt bootstrap_corpus (speech_id)
    in_prebuilt_not_dtm = df_prebuilt[~df_prebuilt.speech_id.isin(df_dtm.u_id)]
    in_dtm_not_prebuilt = df_dtm[~df_dtm.u_id.isin(df_prebuilt.speech_id)]
    assert in_prebuilt_not_dtm.empty, f"bootstrap_corpus has {len(in_prebuilt_not_dtm)} speech_ids not in DTM"
    assert in_dtm_not_prebuilt.empty, f"DTM has {len(in_dtm_not_prebuilt)} speech_ids not in bootstrap_corpus"
