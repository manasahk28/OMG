Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "c:\Users\user\Downloads\OMG"
WshShell.Run """c:\Users\user\Downloads\OMG\venv\Scripts\pythonw.exe"" focus_monitor.py", 0, False
