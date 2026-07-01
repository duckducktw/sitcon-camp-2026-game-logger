#!/bin/bash

# 1. Declare the associative array (dictionary)
declare -A dict

# 2. Read the file into the dictionary
# Assuming file.txt is formatted as key:value or key value
while IFS=":" read -r key value; do
    dict["$key"]="$value"
done < "questions.json"

# 3. Get the dictionary length
echo "The dictionary has ${#dict[@]} items."
