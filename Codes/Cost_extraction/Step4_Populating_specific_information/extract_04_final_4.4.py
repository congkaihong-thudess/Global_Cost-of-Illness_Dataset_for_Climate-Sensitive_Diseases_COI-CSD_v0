# -*- coding: utf-8 -*-

import os
import json
import time
import re
import random
import requests
import pandas as pd
import multiprocessing as mp
from tqdm import tqdm
from typing import Tuple, Optional, Dict, Any, List

# ======================================================
# DeepSeek API
# ======================================================
api_key = "....."  # API key
api_url = "https://api.deepseek.com/v1/chat/completions"

# ======================================================
COST_XLSX = r".../extracted_cost_data_3rd.xlsx"   # Path of input information (results of extraction step 3)
TABLE_XLSX = r".../output_costs_data_1st.xlsx"   # Path of input information (results of extraction step 1)
PARA_XLSX = r".../output_paragraphs_2nd.xlsx"   # Path of input information (results of extraction step 2)

OUT_XLSX = r".../extraction_final_4.4.xlsx"   # Path of output results


# Parallel computing
# ======================================================
MAX_WORKERS = 4                  # Number of parallel processes, recommend between 2 to 6
REQUEST_TIMEOUT = 180
MAX_RETRIES = 5
BASE_BACKOFF = 1.5
PER_CALL_SLEEP_SEC = 0.2

# Prompt length control
MAX_TABLE_CHARS = 12000
MAX_PARA_CHARS = 12000

# ======================================================
def safe_text(x: Any) -> str:
    if x is None:
        return ""
    # pandas NaN
    try:
        if pd.isna(x):
            return ""
    except Exception:
        pass
    s = str(x)
    if s.strip().lower() == "nan":
        return ""
    return s.strip()


def clip_text(s: str, max_len: int) -> str:
    s = s or ""
    if len(s) <= max_len:
        return s

    return s[:max_len] + "\n[TRUNCATED]\n"

# ======================================================
def extract_first_json_object(text: str) -> Optional[str]:
    if not text:
        return None

    t = text.strip()
    t = t.replace("```json", "").replace("```", "").strip()

    start = t.find("{")
    if start == -1:
        return None

    depth = 0
    in_str = False
    esc = False

    for i in range(start, len(t)):
        ch = t[i]

        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue

        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return t[start:i + 1]

    return None

# ======================================================
def call_deepseek(prompt: str) -> Tuple[Optional[str], Optional[str]]:

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT
            )

            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"], None

            if resp.status_code in (429, 500, 502, 503, 504):

                ra = resp.headers.get("Retry-After")
                if ra and ra.isdigit():
                    wait = int(ra)
                else:
                    wait = BASE_BACKOFF * (2 ** attempt) + random.uniform(0, 0.5)
                time.sleep(wait)
                continue

            return None, f"HTTP_{resp.status_code}"

        except requests.exceptions.RequestException as e:

            wait = BASE_BACKOFF * (2 ** attempt) + random.uniform(0, 0.5)
            time.sleep(wait)
            if attempt == MAX_RETRIES - 1:
                return None, f"REQUEST_EXCEPTION:{type(e).__name__}:{e}"

    return None, "MAX_RETRIES_EXCEEDED"

# ======================================================
def build_prompt(
    doi: str,
    cost_value: str,
    cost_feature: str,
    table_text: str,
    para_text: str
) -> str:

    doi = safe_text(doi)
    cost_value = safe_text(cost_value)
    cost_feature = safe_text(cost_feature)
    table_text = clip_text(safe_text(table_text), MAX_TABLE_CHARS)
    para_text = clip_text(safe_text(para_text), MAX_PARA_CHARS)

    prompt = f"""
Task description:
You are given two inputs for a single disease cost value:
1. A JSON object containing the cost value and its preliminary features;
2. Supplementary text paragraphs with contextual details (e.g., years, regions, populations, cost types).
Your task is to extract and infer the following fields for this cost value from these inputs, in strict adherence to the rules below.

Rules (CRITICAL):
1. Priority order: Use Input 1 first, then Input 2.
2. Adhere rules of inferred fields as shown below.
3. If information is absent or ambiguous → fill NR.
4. Preserve original wording, do not normalize or rephrase without permission.

Inferred fields (Strict enumeration ONLY):
1. cost_caliber_infer:
• Format: “[population unit] [time period]” (e.g., per patient one year).
• Population unit options:
> per patient: per patient, each patient, per case, each case, each individual
> per capita: ONLY if the cost is from total cost divided by the total population (NOT by all patients)
> country/regional total: total country/region, in total for a country/region, state-/province-wide
• Time period options: 
> one year: per year, in one year, annual, yearly
> one month: per month, in one month, monthly
> X years/months: for conditions of more than one year/month
> per course/period: a course of treatment, one period of hospitalization, one episode of nursing, per inpatient admission
> per visit: per visit to clinic/hospital, one diagnosis, consult once
2. cost_direct_infer:
• ONLY these exact values allowed:
  > direct: medical care, hospitalization, nursing, medicines, transport, healthcare services, etc.
  > indirect: productivity loss, income loss, labor loss, household burden, etc.
• NEVER use additional descriptions.
3. cost_insurance_infer:
• ONLY these exact values allowed:
  > Government & compulsory insurance: government/public/social health insurance or compulsory non-governmental insurance
  > Voluntary private insurance: voluntary private/commercial insurance
  > Out-of-pocket: user charges/patient-paid
• Not specified or not applicable → NR.
4. cost_treatment_infer:
• Indirect costs → NR.
• Major treatment select one from these 7 options ONLY:
> Ambulatory care: preventive, curative, and rehabilitative services provided in outpatient settings such as clinics and physician offices
> Inpatient care: all medical services and goods consumed during a hospital stay
> Emergency department care: treatment and rehabilitative services delivered in hospital-based emergency departments
> Nursing facility care: nursing and residential care provided in homes or long-term care facilities
> Dental care: preventive and curative oral health services performed at dental facilities
> Retail pharmaceuticals: medications purchased from retail pharmacies, excluding drugs used in institutions
> General administration: administrative and overhead costs of managing health systems and insurance programs
5. cost_indirect_infer:
• Direct costs → NR.
• Select one from these 5 options ONLY:
  > Absenteeism: income loss due to inability to work
  > Presenteeism: productivity loss caused by working with diseases
  > Premature deaths: potential income loss due to deaths
  > Caregiver burden: income loss caused by the need to take care of patients
  > Social welfare burden: long-term social security and allowance need
• No specific type mentioned → NR.

Output format:
Combine the above information along with the literature_doi, totaling 6 items, to form specific information entry corresponding to each disease cost value. Format the output as JSON: {{cost_caliber_infer ..., cost_direct_infer ..., cost_insurance_infer …, ......, cost_indirect_infer ..., literature_doi ...}}.
For example:
```json
{{
“cost_caliber_infer”: “Country total one year”,
“cost_direct_infer”: “Direct”,
“cost_insurance_infer”: “Government and compulsory insurance”,
“cost_treatment_infer”: “Inpatient care”,
“cost_indirect_infer”: “NR”,
“literature_doi”: “10.1097/mlr.0000000000001745”
}}

INPUT DATA (MUST USE):
Input1_cost_json:
DOI: {doi}
Cost value: {cost_value}
Headers: {cost_feature}

Input2_supplementary_paragraphs:
{para_text}
""".strip()

    return prompt

# ======================================================
def process_one(args: Tuple[int, Dict[str, Any]]) -> Dict[str, Any]:
    i, row = args

    doi = safe_text(row.get("doi", ""))
    cost_value = safe_text(row.get("cost_value", ""))
    cost_feature = safe_text(row.get("cost_feature", ""))

    table_text = safe_text(row.get("json_result", ""))
    para_text = safe_text(row.get("deepseek_response", ""))

    prompt = build_prompt(
        doi=doi,
        cost_value=cost_value,
        cost_feature=cost_feature,
        table_text=table_text,
        para_text=para_text
    )

    api_response, api_err = call_deepseek(prompt)

    time.sleep(PER_CALL_SLEEP_SEC + random.uniform(0, 0.15))

    if not api_response:

        return {
            "processing_status": "API calling failed",
            "api_error": api_err or "NO_RESPONSE",
            "literature_doi": doi,
            "input_cost_value": cost_value,
            "input_headers": cost_feature,
            "original_row_index": i
        }

    # Try to get the first JSON object
    json_text = extract_first_json_object(api_response)
    if not json_text:
        return {
            "processing_status": "JSON parse failed",
            "api_error": "NO_JSON_OBJECT_FOUND",
            "literature_doi": doi,
            "input_cost_value": cost_value,
            "input_headers": cost_feature,
            "original_row_index": i,
            "raw_response_head": api_response[:300]
        }

    # Try to parse JSON
    try:
        parsed = json.loads(json_text)

        parsed.setdefault("literature_doi", doi)

        parsed["processing_status"] = "Success"
        parsed["original_row_index"] = i

        parsed["input_cost_value"] = cost_value
        parsed["input_headers"] = cost_feature

        return parsed

    except Exception as e:
        return {
            "processing_status": "JSON parse failed",
            "api_error": f"JSON_LOADS_ERROR:{type(e).__name__}:{e}",
            "literature_doi": doi,
            "input_cost_value": cost_value,
            "input_headers": cost_feature,
            "original_row_index": i,
            "raw_json_head": json_text[:300],
            "raw_response_head": api_response[:300]
        }

# ======================================================
def main():
    print("Reading data...")
    cost_data = pd.read_excel(COST_XLSX)
    table_data = pd.read_excel(TABLE_XLSX)
    paragraph_data = pd.read_excel(PARA_XLSX)

    merged_data = (
        cost_data
        .merge(table_data, on="doi", how="left")
        .merge(paragraph_data, left_on="doi", right_on="input_doi", how="left")
    )


    if "json_result" not in merged_data.columns:
        for cand in ["Table", "table", "table_text", "original_table", "json_result"]:
            if cand in merged_data.columns:
                merged_data = merged_data.rename(columns={cand: "json_result"})
                break
    if "deepseek_response" not in merged_data.columns:
        for cand in ["Paragraphs", "paragraphs", "para_text", "supplementary", "deepseek_response"]:
            if cand in merged_data.columns:
                merged_data = merged_data.rename(columns={cand: "deepseek_response"})
                break

    print(f"Start to process data, {len(merged_data)} lines in total")

    tasks: List[Tuple[int, Dict[str, Any]]] = []
    for idx, row in merged_data.iterrows():
        tasks.append((int(idx), row.to_dict()))

    cpu = mp.cpu_count()
    workers = min(max(cpu - 1, 1), MAX_WORKERS)
    print(f"CPU cores: {cpu} | Number of parallel processes: {workers}")

    with mp.Pool(workers) as pool:
        results = list(tqdm(
            pool.imap(process_one, tasks),
            total=len(tasks),
            desc="Progress"
        ))

    final_output = pd.DataFrame(results)

    out_dir = os.path.dirname(OUT_XLSX)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    final_output.to_excel(OUT_XLSX, index=False)

    if "processing_status" in final_output.columns:
        success_count = int((final_output["processing_status"] == "Success").sum())
        fail_count = int((final_output["processing_status"] != "Success").sum())
    else:
        success_count = 0
        fail_count = len(final_output)

    print("\nProcess complete!")
    print(f"Success: {success_count} lines")
    print(f"Failed: {fail_count} lines")
    print(f"Saving results to: {OUT_XLSX}")


if __name__ == "__main__":
    mp.freeze_support()
    main()
