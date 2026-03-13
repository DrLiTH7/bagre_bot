Set oShell = CreateObject("WScript.Shell")
Dim strArgs
strArgs = "cmd /c ""C:\Users\Fingolfin\Documents\Projetos\bagre\run\run_bagre.bat"""
oShell.Run strArgs, 0, False