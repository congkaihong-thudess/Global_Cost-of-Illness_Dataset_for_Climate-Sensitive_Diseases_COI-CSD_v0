# -*- coding: utf-8 -*-

# ============================================================
# 1. Prepare for work
# ============================================================

import os
import time
import json
import requests
import pandas as pd
from typing import List
from datetime import datetime
from xml.etree import ElementTree as ET


# ============================================================
# File paths
# ============================================================

xml_folder_path = r".../xml files"   # Path of full text xml files
xlsx_output_path = r".../output_costs_data_1st.xlsx"   # Path of output results
error_dois_path = r".../error_dois_1st.csv"   # Path of error information

api_key = "..."   # API key
api_base_url = "https://api.deepseek.com/v1/chat/completions"
model_name = "deepseek-chat"


# ============================================================
# Prompt
# ============================================================

ai_prompt = """Please analyze the full text of the literature to accurately identify and record any tables or paragraphs of costs, expenses, or economic burdens associated with diseases in the literature.

Part I: identify source tables for disease costs
Analyze the full text of the literature, starting from Table 1 through the last table. Evaluate each table to determine whether it mainly exhibits diseases costs, expenditures, or economic information.
1. Inclusion: a table should be “included” only if it satisfies both inclusion criteria:
(1) It contains keywords such as cost, expense, expenditure, spending, fee, budget, loss, financial, economic, or monetary.
(2) It includes specific currency information (e.g., RMB, Dollars, €, etc.).
2. Exclusion: if either inclusion criterion is not met, or any of the following exclusion criteria satisfies, record “excluded” for this table:
(1) It mainly exhibits clinical, epidemiological, or statistical results, rather than cost, expenditure, or economic results.
(2) It mainly exhibits information of unit prices, cost changes (due to some therapies or experiments), or cost-benefit ratios, rather than existed costs, expenditures, economic burden values.
3. Extract tables: for each table from Table 1 to the last table, if it is “included”, record the complete table information, including table title, headers, all table content (rows), and any table tips or footnotes. Do not omit or fabricate.

Part II: identify source paragraphs for disease costs
If all tables received “excluded” in Part I, proceed to this part; otherwise, skip it. 
Analyze each paragraph in the literature section of “Results”, especially in sub-sections about economic results, determine whether it mainly exhibits diseases costs, expenditures, or economic information.
1. Inclusion: a paragraph should be marked “included” only if it satisfies the criterion:
- It contains keywords such as cost, expense, expenditure, spending, fee, budget, loss, financial, and economic, and includes specific currency information (e.g., RMB, Dollars, €, etc.).
2. Exclusion: If the inclusion criterion is not met, or any of the exclusion criteria satisfies, record “excluded” for this paragraph:
(1) It mainly exhibits clinical, epidemiological, or statistical results.
(2) It mainly exhibits information of unit prices, cost changes (due to some therapies or experiments), or cost-benefit ratios.
3. Extract paragraphs: for each paragraph in the literature section of “Results”, if it is “included”, extract segments in the paragraph containing cost values. Each segment mustn’t exceed 200 English words and mustn’t include any tables.

Part III: template-based output format
1. Output table information: if any tables are extracted, output them sequentially without omission. For each table whose title includes the following content (<Table Name>): (<Column Name 1>; <Column Name 2>; …), output table name, headers, main body row by row, and any tips/footnotes. If no table extracted, output NR.
2. Output paragraph information: if no tables are recorded, but some paragraphs are extracted, output those sequentially. If no paragraph extracted, output NR.
3. Output formatting rules:
(1) Tables: compress the table representation. Column names appear only once; row data are presented as arrays. Do not delete any from the original table.
(2) Paragraphs: store extracted paragraphs in a text array. Each paragraph must include disease names and cost values.
4. Output the results of both parts in JSON format, even if the result is NR:
{disease_names …, table_information …, text_information …};
Nest table structure in table_information: {table_title …, table_header …, table_rows [] [] []…, table_tip …}, each square bracket in table_rows represents a row of the table.
For example:
```json
{
“disease_names”: “heart failure, ischemic heart disease”,
“table_information”: “{
“table_title”: “Table 2: Lifetime Mean Costs, Effectiveness, and Cost-effectiveness Ratios”,
“table_header”: “[“Strategy”, “Heart failure admissions”, “Life expectancy”, “Cost”, “QALYs”]”,
“table_rows”: “[“Enalapril indefinitely”, “2.91”, “6.93 years”, “114778 (86083 to 147136)”, “5.49 (5.47-5.51)”],
[“Enalapril for 2 mo, then sacubitril-valsartan”, “2.48”, “8.10 years”, “139456 (100800 to 168916)”, “6.45 (6.43-6.47)”]”
“table_tip”: “”
},
{
… (such as Table 3)
}”
“text_information”: “NR”
}
```
Or
```json
{
“disease_names”: “diabetes, stroke”,
“table_information”: “NR”,
“text_information”: “[“Paragraph 3: According to the findings of these studies in which patients provided their data, the average cost of an outpatient visit ranged from 5.97 million USD (in Nigeria) to 56.94 million USD 7.41 million (in Iran). Costs of annual outpatient visits were reported in these studies conducted in LMICs (24 million USD in Bangladesh and 85.05 million USD in Iran). In comparison, the annual outpatient visit cost in Nigeria was 26.88 million USD.”, “Paragraph 5: The USA had the highest inpatient costs at 9581 USD annually per patient, while Russia had the lowest at 1497 USD annually. The cost of medicine is the second highest cost component per patient (n = 12, 28%), and it exhibited the same results as the previous cost component, with the United States having the highest cost at 7884 USD yearly per patient and Finland having the lowest cost at 192 USD annually per patient.”]”
}
```
FULL TEXT: 
"""


# ============================================================
# 2. DeepSeek API
# ============================================================

def call_deepseek_api(prompt_text: str, full_text_content: str) -> str:

    full_prompt = prompt_text + "\n\n--- LITERATURE TEXT ---\n" + full_text_content

    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": full_prompt}
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"}
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            api_base_url,
            headers=headers,
            json=payload,
            timeout=300
        )
    except Exception as e:
        print("Error making API call for a file:", str(e))
        return "API_CALL_FAILED"

    if response.status_code != 200:
        print("API call failed with status code:", response.status_code)
        return "API_ERROR"

    try:
        parsed = response.json()
        return parsed["choices"][0]["message"]["content"]
    except Exception as e:
        print("Error parsing API response:", str(e))
        return "API_RESPONSE_NOT_JSON"


# ============================================================
# 3. Main function: process xml files one by one
# ============================================================

xml_files = [
    os.path.join(xml_folder_path, f)
    for f in os.listdir(xml_folder_path)
    if f.lower().endswith(".xml")
]

if not xml_files:
    raise RuntimeError("No .xml files found in the specified folder.")

print(f"Found {len(xml_files)} XML files to process.")

results_list: List[str] = []
doi_list: List[str] = []
error_dois: List[str] = []

processed_count = 0
error_count = 0

for idx, xml_file in enumerate(xml_files, start=1):

    print(f"Processing file {idx}/{len(xml_files)}: {os.path.basename(xml_file)}")

    if idx > 1:
        print("Waiting for 2 seconds before processing next article...")
        time.sleep(2)

    doi = os.path.splitext(os.path.basename(xml_file))[0]
    doi_list.append(doi)

    try:
        with open(xml_file, "rb") as f:
            raw_xml = f.read()

        if not raw_xml:
            results_list.append(json.dumps({
                "literature_doi": doi,
                "error": "XML_FILE_EMPTY"
            }, ensure_ascii=False))
            error_dois.append(doi)
            error_count += 1
            continue

        full_text_content = raw_xml.decode("utf-8", errors="ignore")

        ai_result = call_deepseek_api(ai_prompt, full_text_content)

        if ai_result in {
            "API_CALL_FAILED",
            "API_ERROR",
            "API_RESPONSE_NOT_JSON"
        }:
            results_list.append(json.dumps({
                "literature_doi": doi,
                "error": ai_result
            }, ensure_ascii=False))
            error_dois.append(doi)
            error_count += 1
        else:
            results_list.append(ai_result)
            processed_count += 1

    except Exception as e:
        results_list.append(json.dumps({
            "literature_doi": doi,
            "error": f"FILE_READ_ERROR: {str(e)}"
        }, ensure_ascii=False))
        error_dois.append(doi)
        error_count += 1


print("\nProcessing complete.")
print("Successfully processed:", processed_count)
print("Errors encountered:", error_count)


# ============================================================
# 4. Save results
# ============================================================

output_df = pd.DataFrame({
    "doi": doi_list,
    "json_result": results_list
})

output_df.to_excel(xlsx_output_path, index=False)
print("Results saved to:", xlsx_output_path)

if error_dois:
    pd.DataFrame({"error_doi": error_dois}).to_csv(
        error_dois_path, index=False, encoding="utf-8-sig"
    )
    print("Error DOIs saved to:", error_dois_path)
    print("Total error DOIs:", len(error_dois))
else:
    print("No errors encountered, no error DOI file created.")
