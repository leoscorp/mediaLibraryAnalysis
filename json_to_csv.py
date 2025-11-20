import pandas as pd
import json

with open('fileList.json', 'r', encoding='ANSI') as f:
    json_data = json.load(f)

# Create a pandas DataFrame
df = pd.DataFrame(json_data)

# Export to CSV
df.to_csv('fileList.csv', index=False)

print("JSON data successfully converted to fileList.csv")
