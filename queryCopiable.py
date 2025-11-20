import pandas as pd
import subprocess
import ctypes
import json
import time
import sys
import os

def set_terminal_title_windows(title):
    ctypes.windll.kernel32.SetConsoleTitleW(title)

df = pd.read_csv('fileList.csv')

queryConditions = "WHERE originalFileBackup IS NOT NULL AND NOT instr(filePath, '-trailer.')"

from pandasql import sqldf

query = "SELECT * FROM df " + queryConditions

result_df = sqldf(query, globals())
recordCount=len(result_df)

if recordCount==0:
    input("No records found. Press any key to exit...")
    sys.exit()
else:
    commands=[]
    # Loop through the result DataFrame using itertuples()
    for row in result_df.itertuples():
        # Extract the directory path (including parent directories)
        srcDir_path = os.path.dirname(row.filePath)
        destDir_path = srcDir_path.replace('H:\\HTPC\\embyServer', 'W:')
        newItem = ["robocopy", f"{srcDir_path}", f"{destDir_path}", "/E", "/XO", "/PURGE", "/NP"]
        
        if not newItem in commands:
            commands.append(["robocopy", f"{srcDir_path}", f"{destDir_path}", "/E", "/XO", "/PURGE", "/NP"])
    
    for command in commands:
        set_terminal_title_windows(command[1])
        
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
    
        for line in process.stdout:
            with open("copyNewFilesToEmby.txt", "a") as f:
                f.write(line)

            sys.stdout.write(line)
            sys.stdout.flush()
             
        process.wait()
    os.startfile("copyNewFilesToEmby.txt")

