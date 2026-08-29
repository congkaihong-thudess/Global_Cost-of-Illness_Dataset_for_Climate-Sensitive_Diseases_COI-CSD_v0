# -*- coding: utf-8 -*-

# ============================================================
# 1. Prepare for work
# ============================================================

import os
import re
import json
import time
import requests
import pandas as pd
from lxml import etree
from datetime import datetime
from openpyxl import Workbook


# ============================================================
# API & file paths
# ============================================================

api_key = "....."   # API key
api_endpoint = "https://api.deepseek.com/chat/completions"

xml_folder_path = r".../xml files"   # Path of full text xml files
input_excel_path = r".../output_costs_data_1st.xlsx"   # Path of input information (results of extraction step 1)
output_excel_path = r".../output_paragraphs_2nd.xlsx"   # Path of output results


# ============================================================
# Prompt
# ============================================================

your_prompt = """Please analyze the full text of the literature to accurately identify and record all paragraphs containing information related to the disease costs, including years, regions, population characteristics, cost types, etc.
The input consists of two parts:
1. Disease cost tables extracted from the literature, containing all numerical data related to disease costs, expenses, or economic burdens.
2. The full text of the literature.

Part I: identify paragraphs containing years and regions
1. In the literature section of “Methods”, identify and record paragraphs that contain research period information, normally with terms such as “year”, “decade”, “duration”, “period”, “from...to...”, etc. 
2. In the literature section of “Methods”, identify and record paragraphs that contain research region or spot information, normally with names of country, province, state, region, city, county or hospital. Do not exceed 100 English words in total.

Part II: identify paragraphs containing inflation & base year information
In the literature section of “Methods”, especially in sub-sections about economic analysis, identify and record paragraphs indicating whether cost values were adjusted for inflation, and whether there reported a base year for multi-year costs or adjusting inflation. Such paragraphs normally contain keywords like “inflation”, “base year”, “adjust to”, “convert to”, “price index”, “present value”, etc. Do not exceed 100 English words.

Part III: identify paragraphs describing population characteristics
In the literature sub-section of “population/sample” within section of “Methods”, as well as the sub-section of “population characteristics/baseline results” within “Results”, identify and record sequentially:
1. Paragraphs containing phrases like entire population, patients with <Disease Name>, patients diagnosed with <Disease Name>, etc.
2. Paragraphs containing age groups of population like X-Y years and >X years, or age-related terms such as children, elderly, adults, etc.
3. Paragraphs containing gender-related terms such as male, female, gender-stratified, etc.
4. Paragraphs containing income-related phrases such as low/high income, socioeconomic status, rich/poor, <X dollars per month, etc.
5. Any other paragraphs describing specific population subgroups.
Do not exceed 200 English words in total.

Part IV: identify paragraphs containing disease names and ICD codes
In the literature section of “Methods”, especially in sub-sections defining diseases and population selection criteria, identify and record paragraphs that mention disease names along with their ICD-10 codes. If other coding systems are used (e.g., ICD-9, ICD-9-CM, SNOMED), record those as well. Do not exceed 100 English words.

Part V: identify paragraphs describing cost types
In the literature sub-sections describing cost types and cost calculation methods within section of “Methods”, as well as adjacent paragraphs of extracted cost tables (the first input), identify and record sequentially:
1. Paragraphs containing terms like total cost, direct cost, indirect cost, etc.
2. Paragraphs containing reimbursement-related terms such as medical insurance, commercial insurance, out-of-pocket, self-paid, reimbursed by..., etc.
3. Paragraphs containing medical treatment types for direct costs, such as hospitalization, outpatient, medication, surgery, diagnosis, etc.
4. Paragraphs containing types for indirect costs, such as salary reduction, productivity loss, household burden, etc.
5. Any other paragraphs describing specific cost types.
Do not exceed 300 English words in total.

Part VII: template-based output format
Combine results from six parts above, each part’s records should be merged into a single paragraph. Output these six paragraphs together in the following JSON format: {p_year_region …, p_inflation_base …, p_population …, p_disease …, p_cost_type …, p_caliber_sample …}. For each item, if no paragraphs recorded, output NR.
For example:
```json
{
“p_year_region”: “In brief, 21374 eligible participants with acute myocardial infarction were recruited from 63 hospitals in Kerala, India, from November 2014 to November 2016. In this cross-sectional substudy, individual- and household-level cost data were collected 30 days after hospital discharge from a sample of 2114 respondents from November 2014 to July 2016.”,
“p_inflation_base”: “Costs were assessed in Indian rupees (Rs) and converted into 2015 international dollars based on purchasing power parities published by the World Bank (17.152=international$)13; thus, unless otherwise indicated, all costs reported herein as “$” represent international dollars.”,
“p_population”: “We performed age-stratified (<50 years; 50-70 years; and >70 years) and sex-stratified random sampling of a subset of participants who presented for 30-day follow-up to evaluate microeconomic (ie, individual- and household-level) costs associated with acute myocardial infarction hospitalization.”,
“p_disease”: “As a prespecified substudy of ACS QUIK, the present study collected data on individual- and household-level expenditures associated with acute myocardial infarction.”,
“p_cost_type”: “Inpatient cardiovascular hospitalization costs were calculated as the sum of self-reported spending on hospital admission, diagnostic tests, emergency department, food, treatment, ambulance, surgery, medicine, attendants, travel, and other self-reported inpatient costs. Total health care costs additionally included posthospitalization expenses on physicians, rehabilitation, home care, diagnostic tests, food, medicine, transportation, and other self-reported posthospitalization expenses. Out-of-pocket costs were calculated as the sum of all reported costs minus the total reimbursement by the insurance provider. Inpatient percentages were calculated only among patients with expenses reported.”,
“p_caliber_sample”: “In this cross-sectional substudy, individual- and household-level cost data were collected 30 days after hospital discharge from a sample of 2114 respondents from November 2014 to July 2016. The median (interquartile range) expenditure among respondents was $480.4 ($112.5-$1733.0) per acute myocardial infarction encounter, largely driven by in-hospital expenditures.”
}
```
FULL TEXT: 
"""


# ============================================================
# 2. Function of calling DeepSeek API
# ============================================================

def call_deepseek_api(prompt_text, full_text_content):
    full_prompt = (
        prompt_text
        + "\n\n--- LITERATURE TEXT ---\n"
        + full_text_content
    )

    payload = {
        "model": "deepseek-chat",
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
            api_endpoint,
            headers=headers,
            json=payload,
            timeout=300
        )
    except Exception as e:
        print("Error making API call:", e)
        return "API_CALL_FAILED"

    if response.status_code != 200:
        print("API call failed with status code:", response.status_code)
        return "API_ERROR"

    try:
        parsed = response.json()
        return parsed["choices"][0]["message"]["content"]
    except Exception as e:
        print("Error parsing API response:", e)
        return "API_RESPONSE_NOT_JSON"


# ============================================================
# 3. Main program
# ============================================================

input_data = pd.read_excel(input_excel_path)
xml_filename_col = "doi"
json_result_col = "json_result"

responses = []

for idx, row in input_data.iterrows():
    print(f"Processing row {idx + 1} ...")

    doi = row[xml_filename_col]
    xml_filename = doi.replace("/", "_") + ".xml"
    json_str = row[json_result_col]

    xml_file_path = os.path.join(xml_folder_path, xml_filename)
    if not os.path.exists(xml_file_path):
        responses.append(json.dumps({
            "error": f"XML file not found: {xml_file_path}"
        }, ensure_ascii=False))
        continue

    try:
        with open(xml_file_path, "rb") as f:
            xml_tree = etree.parse(f)
            xml_text = etree.tostring(xml_tree, encoding="unicode")
    except Exception as e:
        responses.append(json.dumps({
            "error": f"XML read error: {str(e)}"
        }, ensure_ascii=False))
        continue

    messages = (
        "PROMPT:\n" + your_prompt +
        "\n\nJSON TABLE DATA:\n" + str(json_str) +
        "\n\nXML FULL TEXT:\n" + xml_text
    )

    ai_result = call_deepseek_api("", messages)

    responses.append(ai_result)
    time.sleep(2)


# ============================================================
# 4. Save results
# ============================================================

output_df = pd.DataFrame({
    "input_doi": input_data[xml_filename_col],
    "deepseek_response": responses
})

output_df.to_excel(output_excel_path, index=False)
print("Processing complete. Output saved to:", output_excel_path)
