import pandas as pd
import subprocess
import ctypes
import json
import time
import sys
import os

                              #####################################
                              ##                                 ##
                              ##  Emby Library Conversion Tool   ##
                              ##    Designed and Written By      ##
                              ##          Leo Wink, Jr.          ##
                              ##                                 ##
                              #####################################
                              
## Arguments:  SQL 'WHERE' Filter, Exec flag (empty for display query results with no execute.)


def set_terminal_title_windows(title):
    ctypes.windll.kernel32.SetConsoleTitleW(title)

def get_media_info(filepath):
        #'-print_format', 'json',  # Request JSON output format
    command = [
        'H:\\ffmpeg\\ffprobe'
         ,'-v', 'error'
         ,'-show_streams'  # Show stream information
         ,'-show_entries'  # Show format information
         ,'format=duration:stream=codec_type,codec_name,width,height'
         ,'-of', 'json=c=1'
         ,filepath
    ]

    try:
        # Execute the ffprobe command
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        
        # Parse the JSON output
        media_info = json.loads(result.stdout)
        return media_info
    except subprocess.CalledProcessError as e:
        print(f"Error calling ffprobe: {e}")
        print(f"Stderr: {e.stderr}")
        return None
    except FileNotFoundError:
        print("Error: ffprobe not found. Ensure it's installed and in your system's PATH.")
        return None
    except json.JSONDecodeError:
        print("Error: Could not decode ffprobe's output as JSON.")
        return None

def get_yes_no_input(prompt):

    while True:
        user_input = input(f"{prompt} (Y/N): ").strip().lower()
        if user_input in ('y', 'yes'):
            return True
        elif user_input in ('n', 'no'):
            return False
        else:
            print("Invalid input. Please enter 'Y' or 'N'.")

def hhmmss_to_seconds(time_str):
    
    try:
        h, m, s = map(int, time_str.split(':'))
        total_seconds = (h * 3600) + (m * 60) + s

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return 0

    else:
        return total_seconds

def is_float(s):

    if s.count('.') == 1:  # Check for exactly one decimal point
        parts = s.split('.')
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return True
    # Handle cases like "123" (integers)
    if s.isdigit():
        print(f"{s} is a digit.")
        return True
    return False

# Replace 'your_file.csv' with the actual path to your CSV file
df = pd.read_csv('fileList.csv')

queryConditions = sys.argv[1]

try:
    queryExec = sys.argv[2]
except IndexError:
    queryExec = ""

if queryExec[:4].lower()=="exec":
    displayOnly=False
elif queryExec=="":
    displayOnly = True
else:
    print("Unknown value for option 'displayOnly'. (\"execute\" | \"\")")
    sys.exit()

from pandasql import sqldf

# Example: Select all data where 'Age' is greater than 25
# Set the default fileSize threshold to 5MB if not provided in the queryConditions
if queryConditions.find('fileSize'):
    query = "SELECT * FROM df " + queryConditions
else:
    query = "SELECT * FROM df " + queryConditions + " AND fileSize > 5000000"

print(query)

result_df = sqldf(query, globals())

recordCount=len(result_df)

if recordCount==0:
    input("No records found. Press any key to exit...")
    sys.exit()
else:
    result_df.to_csv('queriedFileList.csv', index=False)

if displayOnly:
    result_df.to_csv('queriedFileList.csv', index=False)
    os.startfile("queriedFileList.csv")

else:    
    overwriteFlag='-n'
    shutdownWhenFinished=False
    processFiles=get_yes_no_input(f"{recordCount} files found. Process conversions (Y|N)?")

    if processFiles:
        if get_yes_no_input("Shutdown PC when finished (Y|N)?"):
            shutdownWhenFinished=True
    
    with open("commandExport.json", "w") as f:
        f.write("{\"query\": \"" + query + "\", \"commandList\": [")
    
    # Loop through the result DataFrame using itertuples()
    savedSpaceBytes = 0
    totalSavedSpace = 0
    for row in result_df.itertuples():
        if os.path.exists('cancel'):
            print(f"Cancel marker is present.  Canceling process")
            time.sleep(5)
            os.remove('cancel')
            
            if shutdownWhenFinished:
                #os.system("shutdown /s /t 60") 
                os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")

            if get_yes_no_input("Push completed conversions to Emby Prod (Y|N)?"):
                subprocess.run(["python", "queryCopiable.py"])
              
            sys.exit()

        row_index   = row.Index + 1
        row_count   = len(result_df)

        full_path   = f"{row.filePath}"
        rowFileSize = row.fileSize
        original_videoCodecName=row.videoCodecName

        # Extract the filename
        filename             = os.path.basename(full_path)
        
        # Extract the directory path (including parent directories)
        directory_path       = os.path.dirname(full_path)
        
        # Extract the immediate parent directory name
        parent_directory     = os.path.basename(directory_path)
        
        # Extract the immediate parent directory name
        gParent_directory    = os.path.basename(os.path.dirname(directory_path))
    
        # Extract the file extension 
        root, file_extension = os.path.splitext(full_path)
        file_stem = os.path.splitext(filename)[0]
        
        set_terminal_title_windows(f"File {row_index} of {row_count}:  {filename}")
        

        command_object = {"fileId": row.id
                         ,"originalFileBackup": f".\\originalStreams\\{gParent_directory}\\{parent_directory}\\{filename}"
                         ,"originalFileSize"  : f"{rowFileSize}"
                         ,"newFilePath"       : f"{directory_path}\\{file_stem}.mkv"
                         ,"commands"          : [["robocopy"
                                                 , f"{directory_path}\\"
                                                 , f".\\originalStreams\\{gParent_directory}\\{parent_directory}\\"
                                                 , f"{filename}"
                                                 , "/XC", "/XN", "/XO", "/NP", "/ETA", "/MOV"
                                                 ],
                                                 ["ffmpeg.exe", f"{overwriteFlag}", "-hwaccel", "cuda"
                                                 , "-i", f".\\originalStreams\\{gParent_directory}\\{parent_directory}\\{filename}"
                                                 , "-c:v", "hevc_nvenc"
                                                 , "-preset", "p6", "-tune", "hq", "-rc", "vbr", "-cq:v", "28", "-b:v", "0k"
                                                 , "-maxrate:v", "3000k", "-bufsize", "20M", "-rc-lookahead", "20", "-bf", "3"
                                                 , "-c:a", "copy"
                                                 , f"{directory_path}\\{file_stem}.mkv"
                                                 ]]
                         ,"fields_array"      : "[]"
                         ,"values_array"      : "[]"
                         }
    
        if not processFiles:
            with open("commandExport.json", "a") as f:
                if row.Index==0:
                    f.write(f"\n{json.dumps(command_object)}")
                else:
                    f.write(f"\n,{json.dumps(command_object)}")
            
        try:
            if processFiles:
                error_flag=False
                for command in command_object['commands']:
                    process = subprocess.Popen(command,
                                               stdout             = subprocess.PIPE,
                                               stderr             = subprocess.STDOUT,
                                               text               = True,
                                               bufsize            = 1,
                                               universal_newlines = True
                    )
                
                    for line in process.stdout:

                        strLine = str(line)
                        line5   = strLine[:5]
 
                        if line5 == 'frame':
                            intTm      = strLine.find('time=')
                            intTm      = intTm + 5
                            strTime    = line[intTm:intTm+8]
                            intTime    = hhmmss_to_seconds(strTime)
                            strDur     = row.durationSeconds
                            pctDone    = int(intTime / row.durationSeconds * 100)
                            #print(f"{pctDone}% complete")
                            set_terminal_title_windows(f"File {row_index} of {row_count} ({pctDone}%):  {filename}")
                            error_flag = False
                        sys.stdout.write(line)
                        sys.stdout.flush()
                         
                    process.wait()
                     
                    if process.returncode !=0:
                        print(f"Subprocess exited with error code: {process.returncode}", file=sys.stderr)
                        
                        strCommand = str(command)
                        if not strCommand.find("robocopy"):
                            error_flag=True
    
                if not error_flag:
                    file_to_probe = f"{directory_path}\\{file_stem}.mkv" 
                    info = get_media_info(file_to_probe)
                    
                    if info:
                        #print(json.dumps(info, indent=4))
                    
                        new_fileSize_bytes    = os.path.getsize(file_to_probe)
                        _, new_fileExt        = os.path.splitext(file_to_probe)
                        new_videoCodecName    = info['streams'][0]['codec_name']
                        new_audioCodecName    = info['streams'][1]['codec_name']
                        new_frameWidth        = info['streams'][0]['width']
                        new_frameHeight       = info['streams'][0]['height']
                        new_durationSeconds   = int(float(info['format']['duration']))
                        new_formattedDuration = time.strftime('%H:%M:%S', time.gmtime(new_durationSeconds))
                        new_kbps              = int(new_fileSize_bytes * 8 / 1024 / new_durationSeconds)

                        originalFileBackup    = command_object['originalFileBackup']
                        originalFileSize      = command_object['originalFileSize']
                       
                        if int(originalFileSize) < int(new_fileSize_bytes) and not originalFileBackup.find('-trailer.'):
                            #put things back where they were.
                            print(f"This file needs to be reverted. original: {originalFileSize}. new: {new_fileSize_bytes}")
                            try:
                                # Move the file
                                os.remove(file_to_probe)
                                os.rename(originalFileBackup, file_to_probe)
                                os.system(f"echo DO NOT PROCESS> \"{originalFileBackup}\"")
                                new_fileExt        = file_extension
                                new_videoCodecName = original_videoCodecName
                                new_fileSize_bytes = rowFileSize
                                originalFileSize   = 16
                                
                            except FileNotFoundError:
                                print(f"Error: Source file '{source_file}' not found.")
                            except Exception as e:
                                print(f"An error occurred: {e}")
                        
                        else:
                            savedSpaceBytes = int(originalFileSize) - int(new_fileSize_bytes)
                            totalSavedSpace = int(totalSavedSpace)  + (savedSpaceBytes)
                            print(f"{savedSpaceBytes:,} bytes saved by converting; {totalSavedSpace:,} total this session.")
                            time.sleep(5)

                        fields_array = ['filePath'
                                      , 'fileExt'
                                      , 'videoCodecName'
                                      , 'audioCodecName'
                                      , 'frameWidth'
                                      , 'frameHeight'
                                      , 'durationSeconds'
                                      , 'formattedDuration'
                                      , 'fileSize'
                                      , 'kbps'
                                      , 'originalFileBackup'
                                      , 'originalFileSize'
                                      ] 
                        values_array = [file_to_probe
                                      , new_fileExt.replace('.','')
                                      , new_videoCodecName
                                      , new_audioCodecName
                                      , new_frameWidth
                                      , new_frameHeight
                                      , new_durationSeconds
                                      , new_formattedDuration
                                      , new_fileSize_bytes
                                      , new_kbps
                                      , str(f"{originalFileBackup}")
                                      , float(originalFileSize)
                                      ]

                        df.loc[df['id'] == command_object['fileId'], fields_array] = values_array
                        df.to_csv('fileList.csv', index=False)

                        result_df.loc[result_df['id'] == command_object['fileId'], fields_array] = values_array
                        result_df.to_csv('queriedFileList.csv', index=False)
    
                        command_object['fields_array'] = fields_array
                        command_object['values_array'] = values_array
                        
                        with open("commandExport.json", "a") as f:
                            command_object_pretty = json.dumps(command_object, indent=4)
                    
                            if row.Index==0:
                                f.write(f"\n{command_object_pretty}")
                            else:
                                f.write(f"\n,{command_object_pretty}")
                else:
                    input("there was an error, somewhere.")

        except FileNotFoundError:
            print(f"Error: Command '{command[0]}' not found.", file=sys.stderr)
    
        except Exception as e:
            print(f"An error occured: {e}", file=sys.stderr)
    
    
    set_terminal_title_windows("Command")

    with open("commandExport.json", "a") as f:
        f.write(f"\n" + "]}")
    
    
    if shutdownWhenFinished:
        #os.system("shutdown /s /t 60") 
        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")

    if get_yes_no_input("Display command object in Notepad? (Y|N)?"):
        os.startfile("commandExport.json")

    if get_yes_no_input("Push completed conversions to Emby Prod (Y|N)?"):
        subprocess.run(["python", "queryCopiable.py"])    

    