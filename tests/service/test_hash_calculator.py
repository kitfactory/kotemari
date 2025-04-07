import pytest
from pathlib import Path
import hashlib

from kotemari.service.hash_calculator import HashCalculator

# Helper to create temporary files for testing
@pytest.fixture
def setup_hash_test_files(tmp_path: Path):
    file1_content = b"Hello, world!"
    file1_path = tmp_path / "file1.txt"
    file1_path.write_bytes(file1_content)

    file2_content = b"\x00\x01\x02\x03\x04\xff\xfe"
    file2_path = tmp_path / "file2.bin"
    file2_path.write_bytes(file2_content)

    empty_file_path = tmp_path / "empty.txt"
    empty_file_path.touch()

    return {
        "file1": file1_path,
        "content1": file1_content,
        "file2": file2_path,
        "content2": file2_content,
        "empty": empty_file_path
    }

# --- Test calculate_file_hash --- #

def test_calculate_hash_sha256_success(setup_hash_test_files):
    """
    Tests calculating SHA256 hash for existing files.
    既存のファイルの SHA256 ハッシュ計算をテストします。
    """
    # Calculate expected hash manually for verification
    # 検証のために期待されるハッシュを手動で計算します
    expected_hash1 = hashlib.sha256(setup_hash_test_files["content1"]).hexdigest()
    expected_hash2 = hashlib.sha256(setup_hash_test_files["content2"]).hexdigest()
    expected_hash_empty = hashlib.sha256(b"").hexdigest()

    hash1 = HashCalculator.calculate_file_hash(setup_hash_test_files["file1"])
    hash2 = HashCalculator.calculate_file_hash(setup_hash_test_files["file2"], algorithm='sha256')
    hash_empty = HashCalculator.calculate_file_hash(setup_hash_test_files["empty"])

    assert hash1 == expected_hash1
    assert hash2 == expected_hash2
    assert hash_empty == expected_hash_empty

def test_calculate_hash_md5_success(setup_hash_test_files):
    """
    Tests calculating MD5 hash for an existing file.
    既存のファイルの MD5 ハッシュ計算をテストします。
    """
    expected_hash1 = hashlib.md5(setup_hash_test_files["content1"]).hexdigest()
    hash1 = HashCalculator.calculate_file_hash(setup_hash_test_files["file1"], algorithm='md5')
    assert hash1 == expected_hash1

def test_calculate_hash_file_not_found(tmp_path: Path):
    """
    Tests calculating hash for a non-existent file.
    存在しないファイルのハッシュ計算をテストします。
    """
    non_existent_path = tmp_path / "not_a_real_file.dat"
    file_hash = HashCalculator.calculate_file_hash(non_existent_path)
    assert file_hash is None

def test_calculate_hash_invalid_algorithm(setup_hash_test_files):
    """
    Tests calculating hash with an invalid algorithm name.
    無効なアルゴリズム名でのハッシュ計算をテストします。
    """
    file_hash = HashCalculator.calculate_file_hash(setup_hash_test_files["file1"], algorithm='invalid-algo')
    assert file_hash is None

def test_calculate_hash_on_directory(tmp_path: Path):
    """
    Tests calculating hash on a directory (should fail gracefully).
    ディレクトリに対するハッシュ計算をテストします（正常に失敗するはずです）。
    """
    # OSError (or IsADirectoryError) is expected when trying to open('rb') on a dir
    # ディレクトリに対して open('rb') を試行すると OSError（または IsADirectoryError）が期待されます
    dir_path = tmp_path / "a_directory"
    dir_path.mkdir()
    file_hash = HashCalculator.calculate_file_hash(dir_path)
    assert file_hash is None 