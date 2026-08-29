# -*- coding: utf-8 -*-

import json
import time
import requests
import pandas as pd
import multiprocessing as mp
from typing import Optional, List, Tuple

# ===============================
# DeepSeek API
# ===============================
api_key = "....."   # API key
api_url = "https://api.deepseek.com/v1/chat/completions"

# ===============================
# Cost extraction prompt
# ===============================
cost_extraction_prompt = """Task description:
You are given one table at a time, extracted from a health economics study. Table structure, headers, and layout may vary substantially. Your task is not to classify, judge, harmonize, or infer costs. Your task is to systematically extract numeric cost values exactly as reported, row by row, and output one JSON object per extracted cost value.
Objectives are:
1. No missing cost-bearing rows.
2. No hallucination or inference.
3. Minimal token usage.
4. One cost value → one JSON object. Each output object can be directly concatenated into a JSON array.
5. Strictly follow extraction rules. No additional contents are allowed.

Extraction rules:
1. Row-based processing:
> Process table row by row, in original order.
> Skip rows with no numeric cost.
> Never merge multiple rows.
2. One cost per object:
> Extract only one numeric cost per object.
> Prefer mean over median.
> Ignore CI, SD, IQR, ranges, brackets.
3. Currency:
> If USD and other currencies coexist, select USD.
> Otherwise, select reported currency.
> Do not convert.
4. Numeric normalization:
> Each extracted cost value MUST be output as one standalone JSON object with 2 fields: cost_value and cost_feature.
> cost_value = numeric string only.
> Do not scale, include brackets, or uncertainty.

How to construct cost_feature (detailed):
cost_feature is a single semicolon-separated string concatenating all remaining attributes.
Fixed internal order (STRICT): 11 elements inside cost_feature must appear exactly in the following order, even if some are NR: currency_raw; sample_size_raw; cost_caliber_raw; data_country_raw; data_region_raw; data_year_raw; base_year_raw; disease_name_raw; disease_code_raw; cost_category_major_raw; cost_category_minor_raw.
Extract only explicitly stated information, if not reported, fill NR.
> currency_raw: ISO-style currency if identifiable (e.g., USD, CNY, INT$), otherwise NR.
> sample_size_raw: Numeric sample size if stated.
> cost_caliber_raw: Statistical unit if stated (e.g., “mean annual cost per patient”).
> data_country_raw: Country name if explicitly stated.
> data_region_raw: Geographic region/city only (NOT care setting).
> data_year_raw: Study year(s) if stated.
> base_year_raw: Price base year if stated.
> disease_name_raw: English disease name if stated.
> disease_code_raw: ICD code or other classification if stated.

Table Format Indicators:
1. Wide format indicators:
> Multiple cost value columns.
> Column headers represent subgroups, settings, or time periods.
> Each column contains multiple related cost values.
2. Long format indicators:
> Single cost value column.
> Row label provides complete cost classification.
3. Key principle: When analyzing tables, focus on “one column, multiple values share a common attribute.” This attribute becomes the major cost category. Row labels correspond to minor categories.

Cost category hierarchy rules:
1. Core principle: Cost hierarchy is determined dynamically based on table structure, following the “one column, multiple values share a common attribute” rule.
2. Wide format (multiple cost columns): Identify columns containing numeric cost values. Column header → major cost category; Row label → minor cost category.
For example: “Columns: Inpatients, Outpatients”.
Inpatients column contains multiple costs → “Inpatients” is cost_category_major_raw, row label is cost_category_minor_raw.
3. Handling multi-level row hierarchies in wide-format tables: If a wide-format table contains two or more hierarchical levels within the row structure (e.g., section headers + indented sub-rows),
> All applicable row-level categories MUST be preserved
> Concatenate hierarchical row labels using a hyphen (-)
> The concatenated string MUST be placed entirely in cost_category_minor_raw
> Preserve the original wording and order as shown in the table
> Do NOT invent, normalize, or rephrase labels
Example logic (illustrative only):
Higher-level row: Admission facility type; Lower-level row: Township health centers → cost_category_minor_raw = “Admission facility type - Township health centers”.
4. Long format (single cost column): If row label contains hierarchical category (e.g., Direct medical costs – Medicines): cost_category_major_raw = higher-level category; cost_category_minor_raw = specific sub-category.
5. If only one category level: cost_category_major_raw = category; cost_category_minor_raw = NR.
6. General rules:
> Do not invent hierarchy.
> Do not normalize wording, and preserve original terms.

Output Format (STRUCTURE ONLY):
Output these 2 pieces in precise JSON format: {cost_value …, cost_feature …}. For multiple cost values in one form/paragraph, the output should be a single JSON array: [{...}, {...}, ..., {...}].
For example:
```json
[
{
“cost_value”: “150400”,
“cost_feature”: “USD; NR; Mean annual cost per patient; USA; NR; 2018; 2018; Diabetes mellitus; NR; Direct medical costs; Medicines”
}
{
… (another cost value)
}
…
]
INPUT TABLE OR PARAGRAPH:
"""

# ======================================================
# Function of processing each publication
# ======================================================
def process_one(args: Tuple[str, str]) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Return:
    - DataFrame or None
    - failed DOI or None
    """
    doi, text = args
    print(f"Processing: {doi}")

    full_prompt = cost_extraction_prompt + text

    request_body = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": full_prompt}],
        "max_tokens": 8000,
        "temperature": 0.2
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        resp = requests.post(api_url, headers=headers, data=json.dumps(request_body), timeout=180)

        if resp.status_code != 200:
            print(f"WARNING: API failed for DOI {doi}, status {resp.status_code}")
            return None, doi

        json_output = resp.json()["choices"][0]["message"]["content"]
        json_output = json_output.replace("```json", "").replace("```", "").strip()

        cost_data = json.loads(json_output)

        if isinstance(cost_data, list) and len(cost_data) > 0:
            df = pd.DataFrame(cost_data)
            df["doi"] = doi
            return df, None
        else:
            return None, None

    except Exception as e:
        print(f"WARNING: Exception for DOI {doi}: {e}")
        return None, doi

    finally:
        time.sleep(1)


# ======================================================
# Main program (including parallel computing)
# ======================================================
def main_processing(input_file: str, output_file: str) -> pd.DataFrame:

    print("Reading Excel file...")
    data = pd.read_excel(input_file)

    if data.shape[1] < 2:
        raise ValueError("The Excel file must contain at least two columns: DOI and text")

    tasks = [
        (str(data.iloc[i, 0]), str(data.iloc[i, 1]))
        for i in range(len(data))
        if pd.notna(data.iloc[i, 1]) and str(data.iloc[i, 1]).strip() != ""
    ]

    # ===== Automatically determine the number of parallel processes =====
    cpu_cores = mp.cpu_count()
    workers = min(cpu_cores - 1, 4)
    workers = max(workers, 1)

    print(f"CPU cores: {cpu_cores} | Number of parallel processes: {workers}")
    print(f"Publications waiting: {len(tasks)}")

    all_results = []
    failed_dois: List[str] = []

    with mp.Pool(processes=workers) as pool:
        for df, failed in pool.imap_unordered(process_one, tasks):
            if df is not None:
                all_results.append(df)
            if failed is not None:
                failed_dois.append(failed)

    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)
    else:
        final_df = pd.DataFrame(columns=["doi", "cost_value", "cost_feature"])

    print("Saving results to Excel...")
    final_df.to_excel(output_file, index=False)

    print(f"Process complete! Extracted {len(final_df)} cost values.")
    print(f"Results saving to {output_file}")

    if failed_dois:
        failed_df = pd.DataFrame({"doi": sorted(set(failed_dois))})
        failed_file = output_file.replace(".xlsx", "_failed_dois.csv")
        failed_df.to_csv(failed_file, index=False)
        print(f"Failed DOIs saving to: {failed_file}")

    return final_df


# ======================================================
# Run the program
# ======================================================
if __name__ == "__main__":

    mp.freeze_support()

    input_excel = r".../output_costs_data_1st.xlsx"   # Path of input information (results of extraction step 1)
    output_excel = r".../extracted_cost_data_3rd.xlsx"    # Path of output results

    results = main_processing(input_excel, output_excel)
