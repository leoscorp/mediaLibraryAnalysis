import pandas as pd
import json


with open('fileList.json', 'r', encoding='ANSI') as f:
    json_data = json.load(f)


# Sample JSON data (can be loaded from a file or string)
""" 
json_data = [
    {"name": "Alice", "age": 30, "city": "New York"},
    {"name": "Bob", "age": 25, "city": "London"},
    {"name": "Charlie", "age": 35, "city": "Paris"}
] 
"""

# Create a pandas DataFrame
df = pd.DataFrame(json_data)

# Export to CSV
df.to_csv('fileList.csv', index=False)

print("JSON data successfully converted to fileList.csv")