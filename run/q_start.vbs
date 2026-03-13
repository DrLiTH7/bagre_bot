Set oShell = CreateObject("WScript.Shell")
Dim strArgs
strArgs = "cmd /c ""C:\bagre\run\run_bagre.bat"""
oShell.Run strArgs, 0, False