# EXAMPLE FILE: copy it to "app_paths.py" and put your own applications.
# "app_paths.py" is ignored by Git, because it contains personal paths.
#
# name -> ( software path , process name or None , [aliases] )
#
# - name:          the main name the AI uses (lowercase, no spaces)
# - software path: path to the .exe, or a link such as steam://rungameid/<game id>
# - process name:  used to close the application (see it in the Task Manager, "Details" tab).
#                  Use None if Jarvis must NOT be allowed to close it.
# - aliases:       other ways to call the application ([] if none)
applications = {
    "steam":   (r"C:\Program Files (x86)\Steam\steam.exe", "steam.exe", []),
    "browser": (r"C:\Users\YOUR_NAME\AppData\Local\Programs\Opera GX\opera.exe", "opera.exe", ["opera", "internet"]),
    "vscode":  (r"C:\Users\YOUR_NAME\AppData\Local\Programs\Microsoft VS Code\Code.exe", "Code.exe", ["visual studio code", "code"]),
    "my_game": (r"steam://rungameid/123456", None, ["game"]),   # Steam game: the id is in the game's store URL
}