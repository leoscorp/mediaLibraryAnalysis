import sys
import os
import shutil

sourcePath = sys.argv[1]
destPath   = sys.argv[2]

try:
    if os.path.exists(sourcePath) and os.path.exists(destPath):
        destFolder = os.path.dirname(destPath)
        srcFolder  = os.path.dirname(sourcePath)
        if os.path.getsize(sourcePath) > 50:
            os.remove(destPath)
            shutil.move(sourcePath, destFolder)
            print(f"moved {sourcePath} to folder {destFolder}")
        else:
            with open(sourcePath, 'r') as file:
                file_content = file.read().replace('\n','')
                input(f"removing the placeholder, {file_content}: {sourcePath}")
            os.remove(sourcePath)
    else:
        input(f"a path is missing. {sourcePath}, {destPath}")

except Exception as e:
    # This is a general exception handler that catches any other unexpected errors
    input(f"An unexpected error occurred: {e}")



