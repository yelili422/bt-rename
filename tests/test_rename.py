import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from bt_rename.rename import (
        fetch_paths_recursively,
    )
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

# Test dataset paths
TEST_DATASET_DIR = os.path.join(os.path.dirname(__file__), '_test_dataset')
DIR1_PATH = os.path.join(TEST_DATASET_DIR, 'dir1')
DIR2_PATH = os.path.join(TEST_DATASET_DIR, 'dir2')


class TestFetchPathsRecursively:
    def test_fetch_dir1_structure(self):
        paths = fetch_paths_recursively(DIR1_PATH, max_depth=2)
        print(paths)
        assert set(paths) == {
            os.path.join(DIR1_PATH, 'S01E01.mkv'),
            os.path.join(DIR1_PATH, 'SPs'),
        }

    def test_fetch_dir2_structure(self):
        paths = fetch_paths_recursively(DIR2_PATH, max_depth=2)
        assert set(paths) == {
            os.path.join(DIR2_PATH, 'Season 1', 'SPs'),
            os.path.join(DIR2_PATH, 'Season 2', 'S02E01.mkv'),
        }