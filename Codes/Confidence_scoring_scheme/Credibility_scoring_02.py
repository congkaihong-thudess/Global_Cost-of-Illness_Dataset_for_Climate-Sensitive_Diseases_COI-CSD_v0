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
cost_extraction_prompt = """Based on the extracted data_source, sample_size, and calculation_methodology from the previous step, rewrite them into the following compact format without losing factual correctness. Do not introduce new information not explicitly present in the extracted fields.

1. data_source_infer: Choose only from these four types: 
> “national official health accounts or disease database”;
> “national/multi-regional surveys or case collection”; 
> “one region official health accounts or disease database”;
> “one region/hospital survey or case collection”. 
Other types are prohibited to fill in. If multiple sources exist, fill only the most dominant one.

2. sample_size_infer: Keep only the numeric value (integer or range). Remove words like “patients”, “participants”, “approximately”. Examples: 12450, 8000–12000, ~45000.

3. calculation_methodology_infer: Choose only from these four types: 
> “top-down account decomposition” for systematically and top-down decomposing the health account to obtain costs;
> “bottom-up microcosting or sampling mean” for bottom-up summarizing or averaging the costs of multiple samples from a cohort or case database;
> “Separated single data” for the costs obtained from a single patient, a single visit, or a single trial; 
> “model output data” for the cost calculated or estimated from the model, not the actual cost incurred. 
Other types are prohibited to fill in. If multiple sources exist, fill only the most dominant one.

Rules:
1. Do not change doi.
2. If the original field is NR, output NR in the short version.
3. sample_size_infer must be number or string (if range like 8000–12000 keep as string).
4. Keep all outputs parsable, deterministic, and conservative (no hallucination).

Output format: JSON only, same keys as input.
Example:
json
{
  “doi”: “10.1001/jama.2022.18456”,
  “data_source_infer”: “national/multi-regional surveys or case collection”,
  “sample_size_infer”: 12450,
  “calculation_methodology_infer”: “bottom-up microcosting or sampling mean”
}

INPUT:
"""


# ======================================================
# Process each publication
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
            print(f"Response text: {resp.text[:200]}")
            return None, doi

        json_output = resp.json()["choices"][0]["message"]["content"]
        print(f"API return (200 characters): {json_output[:200]}")

        json_output = json_output.replace("```json", "").replace("```", "").strip()

        try:
            cost_data = json.loads(json_output)
        except json.JSONDecodeError as je:
            print(f"JSON parsing failed for DOI {doi}: {je}")
            print(f"Original return: {json_output[:500]}")
            return None, doi

        if isinstance(cost_data, dict):

            row_data = {
                "doi": doi,
                "data_source_infer": cost_data.get("data_source_infer", "NR"),
                "sample_size_infer": cost_data.get("sample_size_infer", "NR"),
                "calculation_methodology_infer": cost_data.get("calculation_methodology_infer", "NR")
            }
            df = pd.DataFrame([row_data])
            print(f"Successfully process DOI {doi}: {row_data}")
            return df, None

        elif isinstance(cost_data, list) and len(cost_data) > 0:

            first_item = cost_data[0]
            row_data = {
                "doi": doi,
                "data_source_infer": first_item.get("data_source_infer", "NR"),
                "sample_size_infer": first_item.get("sample_size_infer", "NR"),
                "calculation_methodology_infer": first_item.get("calculation_methodology_infer", "NR")
            }
            df = pd.DataFrame([row_data])
            print(f"Successfully process DOI {doi} (List format): {row_data}")
            return df, None
        else:
            print(f"WARNING: unresolvable data format for DOI {doi}: {type(cost_data)}")
            return None, doi

    except Exception as e:
        print(f"WARNING: Exception for DOI {doi}: {e}")
        import traceback
        traceback.print_exc()
        return None, doi

    finally:
        time.sleep(1)


# ======================================================
# Main program (parallel computing)
# ======================================================
def main_processing(input_file: str, output_file: str) -> pd.DataFrame:
    print("Reading Excel file...")
    data = pd.read_excel(input_file)
    print(f"Original data shape: {data.shape}")
    print(f"Name of columns: {data.colum}")

    if data.shape[1] < 2:
        raise ValueError("Excel files should contain two columns: DOI and text")

    tasks = [
        (str(data.iloc[i, 0]), str(data.iloc[i, 1]))
        for i in range(len(data))
        if pd.notna(data.iloc[i, 1]) and str(data.iloc[i, 1]).strip() != ""
    ]

    print(f"Build {len(tasks)} tasks")

    # ===== Automatically determine the number of parallel computing processes =====
    cpu_cores = mp.cpu_count()
    workers = min(cpu_cores - 1, 4)
    workers = max(workers, 1)

    print(f"CPU cores: {cpu_cores} | Number of parallel processes: {workers}")
    print(f"Literature waiting: {len(tasks)}")

    all_results = []
    failed_dois: List[str] = []

    with mp.Pool(processes=workers) as pool:
        for i, (df, failed) in enumerate(pool.imap_unordered(process_one, tasks)):
            print(f"Progress: {i + 1}/{len(tasks)}")
            if df is not None:
                all_results.append(df)
                print(f"  Successfully added results, current total count: {len(all_results)}")
            if failed is not None:
                failed_dois.append(failed)
                print(f"  Failed DOI: {failed}")

    print(f"Collect {len(all_results)} success results")

    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)

        required_columns = ["doi", "data_source_infer", "sample_size_infer", "calculation_methodology_infer"]
        for col in required_columns:
            if col not in final_df.columns:
                final_df[col] = "NR"

        final_df = final_df[required_columns]
        print(f"Final shape of DataFrame: {final_df.shape}")
        print(f"The first few lines of the final DataFrame:\n{final_df.head()}")
    else:
        print("Warning: No data was successfully extracted!")
        final_df = pd.DataFrame(
            columns=["doi", "data_source_infer", "sample_size_infer", "calculation_methodology_infer"])

    print("Saving results to Excel file...")
    final_df.to_excel(output_file, index=False)

    print(f"Process complete! Extracted {len(final_df)} cost values")
    print(f"Results saving to: {output_file}")

    if failed_dois:
        failed_df = pd.DataFrame({"doi": sorted(set(failed_dois))})
        failed_file = output_file.replace(".xlsx", "_failed_dois.csv")
        failed_df.to_csv(failed_file, index=False)
        print(f"Failed DOI saved to: {failed_file}")
        print(f"Failed DOI list: {sorted(set(failed_dois))}")

    return final_df


# ======================================================
# Run the program
# ======================================================
if __name__ == "__main__":
    mp.freeze_support()

    input_excel = r".../confidence_info_xml.xlsx"
    output_excel = r".../confidence_infer_xml.xlsx"

    results = main_processing(input_excel, output_excel)