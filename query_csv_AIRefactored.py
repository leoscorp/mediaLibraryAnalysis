import pandas as pd
import subprocess
import ctypes
import json
import time
import sys
import os
import logging
import argparse
from pathlib import Path
from pandasql import sqldf

#####################################
##                                 ##
##  Emby Library Conversion Tool   ##
##    Designed and Written By      ##
##          Leo Wink, Jr.          ##
##                                 ##
#####################################

# ==================== CONFIGURATION ====================
FFPROBE_PATH = 'H:\\ffmpeg\\ffprobe'
FFMPEG_PATH = 'ffmpeg.exe'
CSV_FILE = 'fileList.csv'
QUERY_RESULTS_FILE = 'queriedFileList.csv'
COMMAND_EXPORT_FILE = 'commandExport.json'
BACKUP_BASE_PATH = '.\\originalStreams'
DEFAULT_FILESIZE_THRESHOLD = 5000000
CANCEL_MARKER = 'cancel'

# NVENC encoding settings
NVENC_PRESET = 'p6'
NVENC_TUNE = 'hq'
NVENC_CQ = '28'
NVENC_MAXRATE = '3000k'
NVENC_BUFSIZE = '20M'
NVENC_LOOKAHEAD = '20'
NVENC_BFRAMES = '3'

# Required CSV columns
REQUIRED_COLUMNS = ['id', 'filePath', 'fileSize', 'videoCodecName', 'durationSeconds']

# ==================== LOGGING SETUP ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('conversion.log'),
        logging.StreamHandler()
    ]
)


# ==================== UTILITY FUNCTIONS ====================
def set_terminal_title_windows(title):
    """Set the Windows terminal title."""
    try:
        ctypes.windll.kernel32.SetConsoleTitleW(title)
    except Exception as e:
        logging.warning(f"Could not set terminal title: {e}")


def get_yes_no_input(prompt):
    """Get a yes/no response from the user."""
    while True:
        user_input = input(f"{prompt} (Y/N): ").strip().lower()
        if user_input in ('y', 'yes'):
            return True
        elif user_input in ('n', 'no'):
            return False
        else:
            print("Invalid input. Please enter 'Y' or 'N'.")


def hhmmss_to_seconds(time_str):
    """Convert HH:MM:SS format to seconds."""
    try:
        parts = time_str.split(':')
        if len(parts) != 3:
            raise ValueError(f"Expected HH:MM:SS format, got: {time_str}")
        h, m, s = map(int, parts)
        return (h * 3600) + (m * 60) + s
    except ValueError as e:
        logging.error(f"Error parsing time string: {e}")
        return 0


def validate_where_clause(where_clause):
    """
    Basic validation of WHERE clause to prevent SQL injection.
    This is a simple check - for production use, consider more robust validation.
    """
    dangerous_keywords = ['DROP', 'DELETE', 'INSERT', 'UPDATE', 'CREATE', 'ALTER', '--', ';']
    clause_upper = where_clause.upper()
    
    for keyword in dangerous_keywords:
        if keyword in clause_upper:
            logging.error(f"Dangerous SQL keyword detected in WHERE clause: {keyword}")
            return False
    return True


def validate_dataframe(df):
    """Validate that the DataFrame has all required columns."""
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_columns:
        logging.error(f"CSV missing required columns: {missing_columns}")
        return False
    return True


# ==================== MEDIA PROCESSING FUNCTIONS ====================
def get_media_info(filepath):
    """Get media information using ffprobe."""
    command = [
        FFPROBE_PATH,
        '-v', 'error',
        '-show_streams',
        '-show_entries',
        'format=duration:stream=codec_type,codec_name,width,height',
        '-of', 'json=c=1',
        filepath
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        media_info = json.loads(result.stdout)
        return media_info
    except subprocess.CalledProcessError as e:
        logging.error(f"Error calling ffprobe: {e}")
        logging.error(f"Stderr: {e.stderr}")
        return None
    except FileNotFoundError:
        logging.error(f"Error: ffprobe not found at {FFPROBE_PATH}")
        return None
    except json.JSONDecodeError:
        logging.error("Error: Could not decode ffprobe's output as JSON")
        return None


def build_conversion_command(row, gparent_dir, parent_dir, filename, 
                            file_stem, directory_path, overwrite_flag):
    """Build the ffmpeg conversion command object."""
    backup_path = f"{BACKUP_BASE_PATH}\\{gparent_dir}\\{parent_dir}"
    
    return {
        "fileId": row.id,
        "originalFileBackup": f"{backup_path}\\{filename}",
        "originalFileSize": f"{row.fileSize}",
        "newFilePath": f"{directory_path}\\{file_stem}.mkv",
        "commands": [
            # Robocopy command to backup original file
            [
                "robocopy", 
                f"{directory_path}\\",
                f"{backup_path}\\",
                f"{filename}", 
                "/XC", "/XN", "/XO", "/NP", "/ETA", "/MOV"
            ],
            # FFmpeg conversion command
            [
                FFMPEG_PATH, 
                f"{overwrite_flag}", 
                "-hwaccel", "cuda",
                "-i", f"{backup_path}\\{filename}",
                "-c:v", "hevc_nvenc",
                "-preset", NVENC_PRESET,
                "-tune", NVENC_TUNE,
                "-rc", "vbr",
                "-cq:v", NVENC_CQ,
                "-b:v", "0k",
                "-maxrate:v", NVENC_MAXRATE,
                "-bufsize", NVENC_BUFSIZE,
                "-rc-lookahead", NVENC_LOOKAHEAD,
                "-bf", NVENC_BFRAMES,
                "-c:a", "copy",
                f"{directory_path}\\{file_stem}.mkv"
            ]
        ],
        "fields_array": "[]",
        "values_array": "[]"
    }


def should_revert_conversion(original_size, new_size, backup_path):
    """Determine if conversion should be reverted based on size increase."""
    # Don't revert trailers even if they got bigger
    if '-trailer.' in backup_path:
        return False
    return int(original_size) < int(new_size)


def revert_conversion(new_file_path, backup_path):
    """Revert a conversion by restoring the original file."""
    try:
        if os.path.exists(new_file_path):
            os.remove(new_file_path)
        os.rename(backup_path, new_file_path)
        # Create a marker file to prevent reprocessing
        os.system(f'echo DO NOT PROCESS> "{backup_path}"')
        logging.info(f"Reverted conversion: {new_file_path}")
        return True
    except FileNotFoundError:
        logging.error(f"Error: Source file '{backup_path}' not found")
        return False
    except Exception as e:
        logging.error(f"An error occurred during reversion: {e}")
        return False


def update_csv_with_conversion_results(df, result_df, file_id, fields, values):
    """Update both CSV files with conversion results."""
    df.loc[df['id'] == file_id, fields] = values
    df.to_csv(CSV_FILE, index=False)
    
    result_df.loc[result_df['id'] == file_id, fields] = values
    result_df.to_csv(QUERY_RESULTS_FILE, index=False)


def process_conversion_output(process, row, row_index, row_count, filename):
    """Process and display ffmpeg output with progress tracking."""
    error_flag = False
    
    for line in process.stdout:
        str_line = str(line)
        line_prefix = str_line[:5]
        
        # Track progress from ffmpeg frame output
        if line_prefix == 'frame':
            time_index = str_line.find('time=')
            if time_index != -1:
                time_index += 5
                time_str = line[time_index:time_index+8]
                current_seconds = hhmmss_to_seconds(time_str)
                
                if row.durationSeconds > 0:
                    pct_done = int(current_seconds / row.durationSeconds * 100)
                    set_terminal_title_windows(
                        f"File {row_index} of {row_count} ({pct_done}%): {filename}"
                    )
        
        sys.stdout.write(line)
        sys.stdout.flush()
    
    process.wait()
    
    # Check for errors (but ignore robocopy exit codes)
    if process.returncode != 0:
        logging.warning(f"Subprocess exited with code: {process.returncode}")
        # Note: robocopy has different exit codes that may not indicate failure
        error_flag = True
    
    return error_flag


def execute_commands(command_object, row, row_index, row_count, filename):
    """Execute the conversion commands and handle errors."""
    error_flag = False
    
    for command in command_object['commands']:
        # Skip robocopy errors in final error determination
        is_robocopy = "robocopy" in str(command).lower()
        
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            cmd_error = process_conversion_output(process, row, row_index, row_count, filename)
            
            # Only set error flag for non-robocopy commands
            if cmd_error and not is_robocopy:
                error_flag = True
                
        except FileNotFoundError:
            logging.error(f"Error: Command '{command[0]}' not found")
            error_flag = True
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            error_flag = True
    
    return error_flag


def handle_conversion_results(command_object, directory_path, file_stem, 
                             row, original_video_codec, file_extension):
    """Handle post-conversion validation and CSV updates."""
    file_to_probe = f"{directory_path}\\{file_stem}.mkv"
    info = get_media_info(file_to_probe)
    
    if not info:
        logging.error(f"Could not get media info for {file_to_probe}")
        return None
    
    # Extract new file information
    new_filesize = os.path.getsize(file_to_probe)
    _, new_file_ext = os.path.splitext(file_to_probe)
    new_video_codec = info['streams'][0]['codec_name']
    new_audio_codec = info['streams'][1]['codec_name']
    new_width = info['streams'][0]['width']
    new_height = info['streams'][0]['height']
    new_duration = int(float(info['format']['duration']))
    new_formatted_duration = time.strftime('%H:%M:%S', time.gmtime(new_duration))
    new_kbps = int(new_filesize * 8 / 1024 / new_duration)
    
    original_backup = command_object['originalFileBackup']
    original_size = command_object['originalFileSize']
    
    # Check if conversion made file larger and should be reverted
    if should_revert_conversion(original_size, new_filesize, original_backup):
        logging.warning(f"Reverting conversion - new file larger than original")
        logging.info(f"Original: {original_size} bytes, New: {new_filesize} bytes")
        
        if revert_conversion(file_to_probe, original_backup):
            # Use original file stats
            new_file_ext = file_extension
            new_video_codec = original_video_codec
            new_filesize = row.fileSize
            original_size = 16  # Marker value
            space_saved = 0
        else:
            return None
    else:
        # Calculate space saved
        space_saved = int(original_size) - int(new_filesize)
        logging.info(f"Space saved: {space_saved:,} bytes")
        time.sleep(5)
    
    # Prepare update arrays
    fields_array = [
        'filePath', 'fileExt', 'videoCodecName', 'audioCodecName',
        'frameWidth', 'frameHeight', 'durationSeconds', 'formattedDuration',
        'fileSize', 'kbps', 'originalFileBackup', 'originalFileSize'
    ]
    
    values_array = [
        file_to_probe,
        new_file_ext.replace('.', ''),
        new_video_codec,
        new_audio_codec,
        new_width,
        new_height,
        new_duration,
        new_formatted_duration,
        new_filesize,
        new_kbps,
        str(original_backup),
        float(original_size)
    ]
    
    return {
        'fields': fields_array,
        'values': values_array,
        'space_saved': space_saved
    }


def check_for_cancel():
    """Check if cancel marker exists."""
    return os.path.exists(CANCEL_MARKER)


def handle_cancellation(shutdown_when_finished):
    """Handle cancellation request."""
    logging.info("Cancel marker detected - stopping process")
    time.sleep(5)
    
    if os.path.exists(CANCEL_MARKER):
        os.remove(CANCEL_MARKER)
    
    if shutdown_when_finished:
        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
    
    if get_yes_no_input("Push completed conversions to Emby Prod (Y|N)?"):
        subprocess.run(["python", "queryCopiable.py"])


# ==================== MAIN PROCESSING LOOP ====================
def process_files(result_df, df, process_files_flag, shutdown_when_finished):
    """Main processing loop for file conversions."""
    overwrite_flag = '-n'
    total_saved_space = 0
    row_count = len(result_df)
    
    # Initialize command export file
    with open(COMMAND_EXPORT_FILE, "w") as f:
        f.write('{"query": "' + query + '", "commandList": [')
    
    for row in result_df.itertuples():
        # Check for cancellation
        if check_for_cancel():
            handle_cancellation(shutdown_when_finished)
            break
        
        # Extract path information using pathlib
        full_path = Path(row.filePath)
        filename = full_path.name
        directory_path = str(full_path.parent)
        parent_directory = full_path.parent.name
        gparent_directory = full_path.parent.parent.name
        file_stem = full_path.stem
        file_extension = full_path.suffix
        
        row_index = row.Index + 1
        set_terminal_title_windows(f"File {row_index} of {row_count}: {filename}")
        
        # Build conversion command
        command_object = build_conversion_command(
            row, gparent_directory, parent_directory, filename,
            file_stem, directory_path, overwrite_flag
        )
        
        # Write command to export file (display-only mode)
        if not process_files_flag:
            with open(COMMAND_EXPORT_FILE, "a") as f:
                prefix = "\n" if row.Index == 0 else "\n,"
                f.write(f"{prefix}{json.dumps(command_object)}")
            continue
        
        # Execute conversion
        logging.info(f"Processing file {row_index}/{row_count}: {filename}")
        error_flag = execute_commands(command_object, row, row_index, row_count, filename)
        
        if error_flag:
            logging.error("Error occurred during conversion")
            input("Press Enter to continue...")
            continue
        
        # Handle conversion results
        results = handle_conversion_results(
            command_object, directory_path, file_stem,
            row, row.videoCodecName, file_extension
        )
        
        if results:
            # Update CSVs
            update_csv_with_conversion_results(
                df, result_df, command_object['fileId'],
                results['fields'], results['values']
            )
            
            # Update command object and export
            command_object['fields_array'] = results['fields']
            command_object['values_array'] = results['values']
            
            with open(COMMAND_EXPORT_FILE, "a") as f:
                prefix = "\n" if row.Index == 0 else "\n,"
                f.write(f"{prefix}{json.dumps(command_object, indent=4)}")
            
            # Track total space saved
            total_saved_space += results['space_saved']
            logging.info(f"Total space saved this session: {total_saved_space:,} bytes")
    
    # Finalize command export file
    with open(COMMAND_EXPORT_FILE, "a") as f:
        f.write("\n]}")
    
    return total_saved_space


# ==================== MAIN EXECUTION ====================
def main():
    """Main entry point for the script."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Emby Library Conversion Tool - Convert video files using NVENC',
        epilog='Example: python query_csv.py "WHERE videoCodecName=\'h264\'" --exec'
    )
    parser.add_argument(
        'where_clause',
        help='SQL WHERE clause for filtering (e.g., "WHERE videoCodecName=\'h264\'")'
    )
    parser.add_argument(
        '--exec',
        action='store_true',
        help='Execute conversions (default: display only)'
    )
    
    args = parser.parse_args()
    
    # Validate WHERE clause for basic SQL injection prevention
    if not validate_where_clause(args.where_clause):
        logging.error("Invalid WHERE clause - potential SQL injection detected")
        sys.exit(1)
    
    # Load CSV file
    try:
        df = pd.read_csv(CSV_FILE)
        logging.info(f"Loaded {len(df)} records from {CSV_FILE}")
    except FileNotFoundError:
        logging.error(f"CSV file not found: {CSV_FILE}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error loading CSV: {e}")
        sys.exit(1)
    
    # Validate DataFrame
    if not validate_dataframe(df):
        sys.exit(1)
    
    # Build and execute query
    global query
    if 'fileSize' in args.where_clause:
        query = f"SELECT * FROM df {args.where_clause}"
    else:
        query = f"SELECT * FROM df {args.where_clause} AND fileSize > {DEFAULT_FILESIZE_THRESHOLD}"
    
    logging.info(f"Executing query: {query}")
    
    try:
        result_df = sqldf(query, globals())
    except Exception as e:
        logging.error(f"Error executing query: {e}")
        sys.exit(1)
    
    record_count = len(result_df)
    
    if record_count == 0:
        logging.info("No records found matching query")
        input("Press Enter to exit...")
        sys.exit()
    
    logging.info(f"Found {record_count} files matching query")
    
    # Save query results
    result_df.to_csv(QUERY_RESULTS_FILE, index=False)
    
    # Display-only mode
    if not args.exec:
        logging.info(f"Display-only mode - results saved to {QUERY_RESULTS_FILE}")
        os.startfile(QUERY_RESULTS_FILE)
        sys.exit()
    
    # Execution mode - confirm with user
    process_files_flag = get_yes_no_input(
        f"{record_count} files found. Process conversions?"
    )
    
    if not process_files_flag:
        logging.info("User cancelled processing")
        sys.exit()
    
    shutdown_when_finished = get_yes_no_input("Shutdown PC when finished?")
    
    # Process files
    total_saved = process_files(result_df, df, process_files_flag, shutdown_when_finished)
    
    # Cleanup and final actions
    set_terminal_title_windows("Command")
    logging.info(f"Processing complete. Total space saved: {total_saved:,} bytes")
    
    if shutdown_when_finished:
        logging.info("Suspending system...")
        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
    
    if get_yes_no_input("Display command object in Notepad?"):
        os.startfile(COMMAND_EXPORT_FILE)
    
    if get_yes_no_input("Push completed conversions to Emby Prod?"):
        subprocess.run(["python", "queryCopiable.py"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("\nProcess interrupted by user")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)