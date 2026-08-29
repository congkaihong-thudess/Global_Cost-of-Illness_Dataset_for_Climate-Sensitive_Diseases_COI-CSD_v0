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


# ============================================================
# File paths
# ============================================================

xml_folder_path = r".../xml_files"   # Path of full text xml files
xlsx_output_path = r".../confidence_info_xml.xlsx"   # Path of output results
error_dois_path = r".../confidence_error_dois_xml.csv"   # Path of error information

api_key = "....."   # API key
api_base_url = "https://api.deepseek.com/v1/chat/completions"
model_name = "deepseek-chat"


# ============================================================
# Prompt
# ============================================================

ai_prompt = """Role & Objective: You are an expert academic data extraction specialist in health economics and clinical research. Your task is to analyze the provided article on disease-related costs and accurately extract exactly four structured metadata fields. Focus exclusively on peer-reviewed economic evaluations, cost-of-illness studies, or healthcare utilization analyses.

Exaction fields and requirements:
1. doi (String | NR)
> Extract the Digital Object Identifier of the article.
> Format: Standard DOI string without URL prefixes (e.g., 10.1016/j.jval.2023.05.002).
> If only a URL is visible, extract the DOI portion. If the DOI is completely absent or unreadable, return NR.

2. data_source (String | Array of Strings | NR)
> Identify the primary database, survey, registry, cohort, or administrative dataset used for the cost analysis.
> Be specific and retain official acronyms/names (e.g., National Inpatient Sample (NIS), Optum Clinformatics Data Mart, Prospective multicenter cohort).
> If multiple independent sources are combined, separate them with semicolons. If the source is vague or unreported, return NR.

3. sample_size (String | NR)
> Extract the final number of participants, patients, or claims included in the cost analysis.
> Prefer a single integer and a word of “patients/participants” representing the total analytic N. If only an approximate value, range, or subgroup breakdown is provided, return it as a descriptive string (e.g., approximately 45,200 patients, 8,000–12,000 patients).
> Do not infer or calculate N from percentages. If missing, return null.

4. calculation_methodology (String | NR)
> Describe precisely how the disease cost figures were derived, aggregated, or standardized.
> Look for explicit methodological terms such as: mean/median cost per patient, bottom-up microcosting, top-down allocation, claims-based charge-to-cost conversion, full account decomposition, inflation adjustment year, PPP/currency conversion, or standardized billing code aggregation.
> Keep the description concise (1 sentence) and technically accurate. If the methodology is not explicitly detailed, return NR.

Constraints:
1. Do not hallucinate, approximate, or infer missing information. If a field is not explicitly stated in the full text, output NR.
2. Ignore funding sources, author affiliations, or secondary citations unless they are explicitly the primary data source for the cost analysis.
3. Ensure the output is parsable JSON. Escape special characters properly if necessary.

Output specification:
1. Return ONLY a valid JSON object. Do not include markdown formatting, explanations, or conversational text.
2. Use exactly the following keys: doi, data_source, sample_size, calculation_methodology.
3. Strictly enforce the data types specified above. Use NR for any field that cannot be confidently extracted from the text.

JSON Example:
{
  “doi”: “10.1001/jama.2022.18456”,
  “data_source”: “National Health and Nutrition Examination Survey (NHANES); Medicare Fee-for-Service Claims”,
  “sample_size”: “12,450 patients”,
  “calculation_methodology”: “Costs were derived using bottom-up microcosting based on standardized unit prices from the Medicare Physician Fee Schedule and hospital cost reports. Values represent mean annual direct medical costs per patient, adjusted to 2022 USD using the Consumer Price Index.”
}
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
        print("Waiting for 0.5 seconds before processing next article...")
        time.sleep(0.5)

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