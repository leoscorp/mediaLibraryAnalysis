# parse_json.py
import json
import sys
import os
import time

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python parse_json.py <json_string_or_filepath>")
        sys.exit(1)

    json_input = sys.argv[1]
    size_input = sys.argv[2]

    try:
        # Check if the input is a file path
        if json_input.endswith(".json") and os.path.exists(json_input):
            with open(json_input, 'r') as f:
                data = json.load(f)
        else:
            # Assume it's a JSON string
            data = json.loads(json_input)

		# print(f"{data}")
		# Example: Accessing a value
        if "streams" in data:
            
            size_input_fmt = size_input 
            data['format']['fileSize'] = size_input
            data['format']['fileSize_fmt'] = size_input_fmt
            data['format']['kbps'] = round(int(size_input)/1024*8/int(float(data['format']['duration'])),0)
            print(f"\"videoCodecName\": \"{data['streams'][0]['codec_name']}\"" 
                 f", \"audioCodecName\": \"{data['streams'][1]['codec_name'] if len(data['streams']) > 1 else 'None'}\"" 
                 f", \"frameWidth\": \"{data['streams'][0]['width']}\""
                 f", \"frameHeight\": \"{data['streams'][0]['height']}\""
                 f", \"durationSeconds\": \"{int(float(data['format']['duration']))}\""
                 f", \"formattedDuration\": \"{time.strftime('%H:%M:%S', time.gmtime(int(float(data['format']['duration']))))}\""
                 f", \"fileSize\": \"{data['format']['fileSize']}\""
                 f", \"kbps\": \"{data['format']['kbps']}\""
				 )
        else:
            print("No 'streams' key found.")

        # You can add more parsing logic here
        # For example, iterate through keys, extract specific values, etc.

    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"Error: JSON file not found at {json_input}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)