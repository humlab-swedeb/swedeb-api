import typing as t

# from .unused.file_utility import (
#     default_data_folder,
#     excel_to_csv,
#     find_folder,
#     find_parent_folder,
#     find_parent_folder_with_child,
#     load_term_substitutions,
#     pickle_compressed_to_file,
#     pickle_to_file,
#     probe_extension,
#     read_excel,
#     read_json,
#     read_textfile,
#     read_textfile2,
#     read_yaml,
#     symlink_files,
#     touch,
#     unpickle_compressed_from_file,
#     unpickle_from_file,
#     update_dict_from_yaml,
#     write_json,
#     write_yaml,
# )
# from .unused.filename_fields import (
#     FilenameFieldSpec,
#     FilenameFieldSpecs,
#     NameFieldSpecs,
#     extract_filename_metadata,
#     extract_filenames_metadata,
# )
# from .unused.filename_utils import (
#     VALID_CHARS,
#     assert_that_path_exists,
#     data_path_ts,
#     filename_satisfied_by,
#     filename_whitelist,
#     filenames_satisfied_by,
#     filter_names_by_pattern,
#     now_timestamp,
#     path_add_date,
#     path_add_sequence,
#     path_add_suffix,
#     path_add_timestamp,
#     path_of,
#     replace_extension,
#     replace_folder,
#     replace_folder_and_extension,
#     strip_extensions,
#     strip_path_and_add_counter,
#     strip_path_and_extension,
#     strip_paths,
#     suffix_filename,
#     timestamp_filename,
#     ts_data_path,
# )
from .pandas_utils import (  # pandas_read_csv_zip,; pandas_to_csv_zip,
    DataFrameFilenameTuple,
    PropertyValueMaskingOpts,
    as_slim_types,
    create_mask,
    create_mask2,
    faster_to_dict_records,
    is_strictly_increasing,
    rename_columns,
    set_default_options,
    set_index,
    size_of,
    try_split_column,
    ts_store,
    unstack_data,
)

# from .unused.pos_tags import (
#     Known_PoS_Tag_Schemes,
#     PD_PoS_tag_groups,
#     PoS_Tag_Scheme,
#     PoS_Tag_Schemes,
#     PoS_TAGS_SCHEMES,
#     get_pos_schema,
#     pos_tags_to_str,
# )
# from .unused._decorators import (  # try_catch,
#     ExpectException,
#     deprecated,
#     do_not_use,
#     enter_exit_log,
#     mark_as_disabled,
#     suppress_error,
# )


# from .unused.paths import find_ancestor_folder, find_data_folder, find_resources_folder, find_root_folder
# from .unused.pivot_keys import PivotKeys, codify_column

# type: ignore
# from .unused import zip_utils


# from .unused.zip_utils import (  # , read_dataframe, read_json
#     compress,
#     list_filenames,
#     read_file_content,
#     store,
#     unpack,
#     zipfile_or_filename,
# )

T = t.TypeVar('T')


# class EmptyDataError(ValueError): ...
