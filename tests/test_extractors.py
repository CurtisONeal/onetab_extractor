import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime
from onetab_extractor import extract_bookmarks, extract_onetab, extract_open_tabs

# Sample Bookmarks Data
BOOKMARKS_JSON = {
    "roots": {
        "bookmark_bar": {
            "type": "folder",
            "name": "bookmark_bar",
            "children": [
                {
                    "type": "url",
                    "name": "Google",
                    "url": "https://google.com",
                    "date_added": "13320000000000000"  # Microseconds since 1601-01-01
                }
            ]
        }
    }
}

# Sample OneTab State Data
ONETAB_STATE = {
    "tabGroups": [
        {
            "label": "Work Project",
            "createDate": 1740000000000,
            "color": "blue",
            "starred": True,
            "locked": False,
            "tabsMeta": [
                {"title": "Jira", "url": "https://jira.com"}
            ]
        }
    ]
}

def test_extract_bookmarks(tmp_path):
    bookmarks_file = tmp_path / "Bookmarks"
    with open(bookmarks_file, "w", encoding="utf-8") as f:
        json.dump(BOOKMARKS_JSON, f)
    
    data = extract_bookmarks(bookmarks_file)
    assert len(data) == 1
    assert data[0]['Source'] == 'Bookmark'
    assert data[0]['Title'] == 'Google'
    assert data[0]['URL'] == 'https://google.com'
    assert "2023" in data[0]['Date Added']  # Rough check of timestamp conversion

def test_extract_onetab(tmp_path):
    # Mocking plyvel because it's hard to create real LevelDB on the fly
    db_path = tmp_path / "onetab_db"
    db_path.mkdir()
    
    with patch('plyvel.DB') as mock_db_class, patch('shutil.copytree'):
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        # Double encoded JSON as observed in OneTab LevelDB
        mock_db.get.return_value = json.dumps(json.dumps(ONETAB_STATE)).encode('utf-8')
        
        data = extract_onetab(db_path, tmp_path)
        
        assert len(data) == 1
        assert data[0]['Source'] == 'OneTab'
        assert data[0]['Category/Group'] == 'Work Project'
        assert data[0]['Title'] == 'Jira'
        assert data[0]['Color'] == 'blue'
        assert 'starred' in data[0]['Metadata']

def test_extract_open_tabs(tmp_path):
    # Create a small dummy SNSS file
    sessions_dir = tmp_path / "Sessions"
    sessions_dir.mkdir()
    session_file = sessions_dir / "Session_123"
    
    # Binary SNSS format: Header 'SNSS' + 4 bytes version + (2 bytes size + 1 byte cmd + data)
    # Simplified mock for robust parser
    # We'll just write some http patterns preceded by length (little-endian 4 bytes)
    url = "http://test.com"
    url_bytes = url.encode('utf-8')
    len_bytes = len(url_bytes).to_bytes(4, 'little')
    
    # Dummy structure: Header 'SNSS' + 4-byte version
    # Then some command: [size (2 bytes), cmd (1 byte), data (rest)]
    # size = 1 (cmd) + len_prefix (4) + data (len)
    size = 1 + 4 + len(url_bytes)
    size_bytes = size.to_bytes(2, 'little')
    
    with open(session_file, "wb") as f:
        f.write(b'SNSS\x01\x00\x00\x00')
        f.write(size_bytes)
        f.write(b'\x01') # dummy command id
        f.write(len_bytes)
        f.write(url_bytes)
    
    data = extract_open_tabs(sessions_dir)
    assert len(data) >= 1
    # Check if our test URL was found
    found = any(item['URL'] == url for item in data)
    assert found
