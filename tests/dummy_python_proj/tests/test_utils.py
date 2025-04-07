import pytest
from my_module import utils # Assuming tests run from project root

def test_process_item():
    assert utils.process_item("abc") == "ABC"
    assert utils.process_item(123) == "123"

# A simple test, more would be needed for load_data (e.g., mocking open)
# 簡単なテスト。load_dataにはさらにテストが必要（例：openのモック） 