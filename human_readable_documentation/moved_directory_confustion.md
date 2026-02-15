
Context:

I moved the project from:
/Users/curtisoneal/OneTabExtractor/

To: 
/Users/curtisoneal/dev/gitrepos/reference/OneTabExtractor/,

and the tpycharm config files,.idea, did not seem to recognize this when I reopend the project in the new location.
The files also wrote to the previous directory.


Thre were some other hard coded values that needed to be adjusted.


While what the coding assistant says below is not 100% here is the quote.

---

```

The issue was caused by the project files being moved while internal paths 
**and IDE configurations** remained pointed at the old directory. 

Specifically, **shortcut** is a symbolic link to 
/Users/curtisoneal/dev/gitrepos/reference/OneTabExtractor/, which is where the actual project files and the .idea folder (IDE settings) are located.

Actions Taken:
1. Updated onetab_extractor.py:
- Changed the default --dir argument from a hardcoded absolute path to os.path.dirname(os.path.abspath(__file__)). This ensures the script always knows where it is located and saves output to its own directory by default, regardless of where you move it.
2. Updated README.md:
- Reflected the code changes in the documentation.
- Updated the recommended shell alias path to point to the current location: /Users/curtisoneal/OneTabExtractor/shortcut.
3. Verification:
- Successfully ran the script using uv run onetab_extractor.py -dr from within the project directory.

**Recommended Steps for You:**:
1. Re-open the Project in the IDE The IDE is "confused" because it might be looking at the parent folder (/Users/curtisoneal/OneTabExtractor/) or the old path.
- Close the current project in your IDE. Open the specific directory: /Users/curtisoneal/dev/gitrepos/reference/OneTabExtractor/ (or use the link /Users/curtisoneal/OneTabExtractor/shortcut). The .idea folder is located there, so the IDE should automatically recognize the project structure and the interpreter (once uv handles the environment).

2. Update your Shell Alias
Update your .zshrc or .bash_profile with the new correct path:
alias getOneTab="uv --directory /Users/curtisoneal/OneTabExtractor/shortcut run onetab_extractor.py"

3. Cleanup (Optional)
There are some stray files and a tmp_onetab_db folder in /Users/curtisoneal/OneTabExtractor/ (the parent of the shortcut). These are likely remnants from previous attempts or old runs and can be safely deleted if you only want to keep the main project in the shortcut target.
Your project is now location-independent regarding its internal logic!
```

Some of what it is seeing are results from my attempt to fix the situation.
