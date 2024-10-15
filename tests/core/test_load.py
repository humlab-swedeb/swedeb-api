# import os
# import shutil
# import time
# import uuid
# from os.path import join

# import pandas as pd

# from api_swedeb.core.configuration.inject import ConfigStore, ConfigValue
# from api_swedeb.core.load import SPEECH_INDEX_DTYPES, load_speech_index, slim_speech_index, is_invalidated

# ConfigStore.configure_context(context="all-data", source="config/config.yml", switch_to_context=False)

# def test_is_invalidated():

#     temp_folder: str = f"tests/output/{str(uuid.uuid4())[:8]}"
#     os.makedirs(temp_folder, exist_ok=True)

#     # Test when target file does not exist
#     source_path: str = f"{temp_folder}/source.txt"
#     target_path: str = f"{temp_folder}/target.txt"
#     assert is_invalidated(source_path, target_path)

#     # Test when source file is older than target file
#     with open(source_path, "w", encoding="utf-8") as f:
#         f.write("Hello")

#     time.sleep(1)
#     with open(target_path, "w", encoding="utf-8") as f:
#         f.write("Hello")

#     assert not is_invalidated(source_path, target_path)

#     # Test when source file is newer than target file
#     time.sleep(1)

#     with open(source_path, "w", encoding="utf-8") as f:
#         f.write("Hello")

#     assert is_invalidated(source_path, target_path)


# def test_speech_index_memory_usage():
#     folder: str = ConfigValue("dtm.folder").resolve("all-data")
#     tag: str = ConfigValue("dtm.tag").resolve("all-data")
#     csv_path: str = join(folder, f"{tag}_document_index.csv.gz")
#     di: pd.DataFrame = pd.read_csv(join(folder, csv_path), sep=';', compression="gzip", index_col=0)
#     memory_after_load = di.memory_usage(deep=True).sum() / 1024**2

#     di = slim_speech_index(di)
#     memory_after_slim = di.memory_usage(deep=True).sum() / 1024**2

#     di = di.astype(SPEECH_INDEX_DTYPES)

#     memory_after_astype = di.memory_usage(deep=True).sum() / 1024**2

#     logger.info(f"Memory usage after load: {memory_after_load:3} MB")
#     logger.info(f"Memory usage after slim: {memory_after_slim:3} MB")
#     logger.info(f"Memory usage after cast: {memory_after_astype:3} MB")

#     assert memory_after_astype < memory_after_load


# def test_load_speech_index():
#     folder: str = ConfigValue("dtm.folder").resolve()
#     tag: str = ConfigValue("dtm.tag").resolve()
#     csv_file = f"{tag}_document_index.csv.gz"
#     feather_file = f"{tag}_document_index.feather"
#     prepped_file = f"{tag}_document_index.prepped.feather"

#     temp_folder: str = f"tests/output/{str(uuid.uuid4())[:8]}"

#     os.makedirs(temp_folder, exist_ok=True)
#     shutil.copyfile(f"{folder}/{csv_file}", f"{temp_folder}/{csv_file}")

#     speech_index = load_speech_index(folder=temp_folder, tag=tag)

#     assert speech_index is not None
#     assert os.path.isfile(f"{temp_folder}/{feather_file}")
#     assert not os.path.isfile(f"{temp_folder}/{prepped_file}")

#     speech_index2 = load_speech_index(folder=temp_folder, tag=tag)
#     assert speech_index2 is not None

#     assert os.path.isfile(f"{temp_folder}/{prepped_file}")
