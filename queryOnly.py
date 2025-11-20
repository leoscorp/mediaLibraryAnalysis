import pandas as pd
import subprocess
import ctypes
import json
import time
import sys
import os

df = pd.read_csv('fileList.csv')

queryConditions = sys.argv[1]
skipTrailer     = sys.argv[2]

if skipTrailer=='-trailer':
    queryConditions = queryConditions.replace("WHERE", "WHERE NOT instr(filePath,'-trailer.') AND")
elif skipTrailer=='+trailer':
    queryConditions = queryConditions.replace("WHERE", "WHERE instr(filePath,'-trailer.') AND")

from pandasql import sqldf

query = "SELECT * FROM df " + queryConditions

print(query)

result_df = sqldf(query, globals())
recordCount=len(result_df)

if recordCount==0:
    input("No records found. Press any key to exit...")
    sys.exit()
else:
    result_df.to_csv("queriedOnlyList.csv", index=False)
    os.startfile("queriedOnlyList.csv")

