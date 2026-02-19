To consolidate Chrome's "open" tabs (grouped and ungrouped) and "bookmarks" into a single CSV alongside your existing OneTab data, you can use the following mechanisms:

### 1. Extracting Bookmarks
Chrome stores bookmarks in a standard JSON file located at:
`~/Library/Application Support/Google/Chrome/Default/Bookmarks`

**Mechanism:** 
*   Use a Python script with the `json` module to parse this file.
*   Recursively traverse the `roots` (e.g., `bookmark_bar`, `other`) to extract the `name`, `url`, and `date_added`.
*   **Columns to include:** `Source` (set to "Bookmark"), `Folder/Group` (the bookmark folder path), `Title`, `URL`, `Date Added`.

### 2. Extracting Open Tabs (Grouped and Ungrouped)
Chrome stores the current session's tabs and tab groups in binary files within the `Sessions` directory:
`~/Library/Application Support/Google/Chrome/Default/Sessions/`
The files are usually named `Tabs_xxxxxxxxxxxxxx` and `Session_xxxxxxxxxxxxxx`.

**Mechanism:**
*   These files use a custom binary format (SNSS). To read them without reinventing the wheel, you can use a library like `browser-history` or specialized Chrome session parsers.
*   Alternatively, you can use the **Chrome DevTools Protocol (CDP)** or a **Chrome Extension** to export currently open tabs to a JSON/CSV file.
*   **Columns to include:** `Source` (set to "Open Tab"), `Group` (the Tab Group title, if any), `Title`, `URL`, `Window ID`.

### 3. Combining into a Unified CSV
To merge all three sources (OneTab, Bookmarks, and Open Tabs), you should normalize the data structure.

**Proposed CSV Structure:**
| Source | Category/Group | Title | URL | Date Created | Metadata (JSON/Misc) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| OneTab | "Work Project" | Google | https://google.com | 2024-02-18 | {"color": "blue"} |
| Bookmark | "Research/AI" | arXiv | https://arxiv.org | 2023-10-12 | {"folder": "AI"} |
| Open Tab | "Travel Planning" | Expedia | https://expedia.com | 2026-02-18 | {"tab_group": "Travel"} |
| Open Tab | *None* | GitHub | https://github.com | 2026-02-18 | {"ungrouped": true} |

### Implementation Strategy
1.  **Python Script Enhancement:** Modify your `onetab_extractor.py` to include functions for `parse_bookmarks()` and `parse_sessions()`.
2.  **Normalization:** Map the unique fields from each source to a common dictionary format.
3.  **CSV Export:** Use `csv.DictWriter` with a superset of all required fieldnames to ensure no data is lost during the merge.
4.  **Handling Binary Files:** For the `Sessions` files, consider copying them to a temporary location (similar to what you do with OneTab's LevelDB) to avoid file lock issues while Chrome is running.