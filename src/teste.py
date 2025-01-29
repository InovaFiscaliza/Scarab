import pandas as pd

df = pd.DataFrame([
  {"mountain": "Mount Everest", "feet": 29029, "location": "Nepal/China"},
  {"mountain": "K2", "feet": 28255, "location": "Pakistan/China"},
  {"mountain": "Kangchenjunga", "feet": 28169, "location": "Nepal/India"},
  {"mountain": "Lhotse", "feet": 27940, "location": "Nepal"},
  {"mountain": "Makalu", "feet": 27838, "location": "Nepal"},
])

# Store the column name in a variable
column_name = "location"

# Use the variable to access the column
result = df[df[column_name].str.contains("Nepal")]

print(result)