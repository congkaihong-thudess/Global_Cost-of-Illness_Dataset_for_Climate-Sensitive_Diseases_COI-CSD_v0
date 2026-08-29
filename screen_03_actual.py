# -*- coding: utf-8 -*-

# ============================================================
# 0. Prepare to work
# ============================================================

import os
import re
import json
import time
import glob
import math
from datetime import datetime
from typing import Optional, Dict, Any, List

import requests
import pandas as pd

from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing


# ============================================================
# 0.2 File path
# ============================================================

PATH_ROOT = r".../third screening"
API_URL = "https://api.deepseek.com/v1/chat/completions"
API_KEY = "....."   # API password


# ============================================================
# 0.3 Test DeepSeek API
# ============================================================

def test_api_functionality(api_key: str) -> str:
    response = requests.post(
        API_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": "deepseek-chat",
            "messages": [
                {"role": "user", "content": "Please answer: is DeepSeek API working normally?"}
            ],
            "temperature": 0.3
        },
        timeout=10
    )

    if response.status_code == 200:
        reply = response.json()["choices"][0]["message"]["content"]
        return f"API is normal! Response reply:{reply}"
    else:
        return f"API call failed, status code:{response.status_code}\n{response.text}"


print(test_api_functionality(API_KEY))


# ============================================================
# 1. Read and batch Excel files
# ============================================================

source_path = os.path.join(PATH_ROOT, "source files")
merged_files = sorted(
    glob.glob(os.path.join(source_path, "literature_after_2nd_step_*.xls"))
)

if not merged_files:
    raise FileNotFoundError("literature_after_2nd_step_*.xls not found")

all_data: List[pd.DataFrame] = []

for file in merged_files:
    df = pd.read_excel(file, dtype=str)
    file_num = re.search(r"\d+", os.path.basename(file)).group(0)
    df["source_files"] = file_num
    df = df.astype(str)
    all_data.append(df)

combined = pd.concat(all_data, ignore_index=True)

savedrecs_keep = ["DOI", "Title", "Abstract", "Source", "source_files"]
combined = combined[[c for c in savedrecs_keep if c in combined.columns]]
combined = combined[combined["DOI"].notna() & (combined["DOI"] != "")]


def collapse_unique(series: pd.Series) -> str:
    vals = [v for v in series if pd.notna(v) and v not in ("nan", "None")]
    return "; ".join(dict.fromkeys(vals))


def collapse_source(series: pd.Series) -> str:
    return ",".join(sorted(set(series)))


combined_final = (
    combined
    .groupby("DOI", as_index=False)
    .agg({
        "Title": collapse_unique,
        "Abstract": collapse_unique,
        "Source": collapse_unique,
        "source_files": collapse_source
    })
)

result_dir = os.path.join(PATH_ROOT, "Result")
output_dir = os.path.join(PATH_ROOT, "Output")
os.makedirs(result_dir, exist_ok=True)
os.makedirs(output_dir, exist_ok=True)

merged_csv = os.path.join(result_dir, "merged_all.csv")
combined_final.to_csv(merged_csv, index=False, encoding="utf-8-sig")


# ============================================================
# 2. Data preprocessing
# ============================================================

def preprocess_data(fp: str) -> pd.DataFrame:
    df = pd.read_csv(fp, dtype=str, encoding="utf-8")
    df = df[["DOI", "Abstract"]]
    df["Abstract"] = df["Abstract"].str.replace(r"\s+", " ", regex=True)
    df = df[df["Abstract"].notna() & (df["Abstract"].str.len() > 50)]
    return df


data = preprocess_data(merged_csv)


# ============================================================
# 3. API function for single publication
# ============================================================

output_error = os.path.join(result_dir, "api_error_log.txt")
output_temp = os.path.join(result_dir, "temp_results.csv")
output_batch_tpl = os.path.join(result_dir, "results_batch_%d.csv")


def classify_abstract(DOI: str, Abstract: str, api_key: str) -> Dict[str, str]:

    prompt = f"""
Analyze the following abstract to determine if the literature is likely to be included, excluded, or unclear based on judging whether the cost/expenditure/economic impacts are actually existed values.

Inclusion criteria (assess each):
1. The main costs, expenditures, or economic burdens considered in the literature are direct costs caused by diseases, such as hospital, outpatient, medication, diagnosis, or transportation costs.
2. The main costs, expenditures, or economic burdens considered in the literature are indirect costs caused by diseases, such as salary loss, labor loss, low life quality induced costs, social welfare loss.

Exclusion criteria (assess each):
1. The main costs, expenditures, or economic burdens considered in the literature are simulated, predicted, or estimated by models such as Markov models, regression analysis, scenario analysis, etc. That is, there is no actual behavior of disease diagnosis & treatment or spending/paying expenses.
2. The main costs, expenditures, or economic burdens considered in the literature are required costs, cost gap, or projected costs, meaning it is not actually incurred or expended costs/expenditures.
3. The main costs, expenditures, or economic burdens considered in the literature are change amounts (cost increases/reductions caused by adopting a certain drug, therapy, or surgery) rather than total amount.
4. The main results considered in the literature are cost-benefit ratios, cost-effectiveness results, or budget adjustments rather than existed cost/expenditure/economic burden values.

For each step, decide one of “satisfied”, “not satisfied”, or “unclear”;

Finally, provide a final decision:
1. If the literature meets one of inclusion criteria and none of the exclusion criteria, output “included”;
2. If the literature meets any one of exclusion criteria, output “excluded”;
3. If the decision cannot be made due to limited information, output “unclear”.

Format output of all criteria as JSON. Use this exact structure, even if answer is “unclear”:
{{Inclusion1 ..., Inclusion2 ..., Exclusion1 ..., ..., Exclusion4 ..., Final_decision ...}}
For example:
```json
{{
“Inclusion1”: “satisfied”,
“Inclusion2”: “not satisfied”,
“Exclusion1”: “not satisfied”,
“Exclusion2”: “not satisfied”,
“Exclusion3”: “not satisfied”,
“Exclusion4”: “not satisfied”,
“Final_decision”: “included”
}}
```
ABSTRACT: {Abstract[:3000]}
"""
    try:
        response = requests.post(
            API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.5,
                "max_tokens": 500
            },
            timeout=30
        )

        print("==== START ====")
        print("DOI:", DOI)
        print("Status Code:", response.status_code)
        print("Raw Response Text:\n", response.text)
        print("==== END ====\n")

        if response.status_code == 200:
            parsed = response.json()
            return {"DOI": DOI, "result": parsed["choices"][0]["message"]["content"]}
        else:
            with open(output_error, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now()} | DOI={DOI}\n{response.text}\n\n")
            return {"DOI": DOI, "result": f"API_ERROR_{response.status_code}"}

    except Exception:
        return {"DOI": DOI, "result": "FAILED_AFTER_RETRY"}


# ============================================================
# 4. Batch processing (automatic parallel computing)
# ============================================================

def process_abstracts(
    data: pd.DataFrame,
    api_key: str,
    batch_size: int = 100,
    delay: float = 1,
    save_every: int = 200,
    initial_save_counter: int = 1
):

    total = len(data)
    results: List[Dict[str, str]] = []
    save_counter = initial_save_counter
    last_saved_index = 0

    max_workers = min(8, multiprocessing.cpu_count())

    for start in range(0, total, batch_size):
        batch = data.iloc[start:start + batch_size]

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(classify_abstract, row.DOI, row.Abstract, api_key)
                for row in batch.itertuples()
            ]

            for future in as_completed(futures):
                results.append(future.result())

        time.sleep(delay)

        pd.DataFrame(results).to_csv(output_temp, index=False, encoding="utf-8-sig")

        if len(results) - last_saved_index >= save_every or start + batch_size >= total:
            new_results = results[last_saved_index:]
            batch_df = pd.DataFrame(new_results)
            batch_file = output_batch_tpl % save_counter
            batch_df.to_csv(batch_file, index=False, encoding="utf-8-sig")
            print(f"Saving {batch_file}(Add {len(batch_df)} pieces)")
            last_saved_index = len(results)
            save_counter += 1

        processed = min(start + batch_size, total)
        print(f"Processed {processed}/{total} ({200 * processed / total:.1f}%)...")

    return pd.DataFrame(results)


# ============================================================
# 5. Execute (resume from breakpoint)
# ============================================================

if os.path.exists(output_temp):
    completed = pd.read_csv(output_temp)["DOI"].tolist()
    print(f"{len(completed)} records completed, and will skip")
else:
    completed = []
    print("Completed records not found, will process from the beginning")

remaining = data[~data["DOI"].isin(completed)]
initial_save_counter = math.ceil(len(completed) / 200) + 1

results_df = process_abstracts(
    remaining,
    API_KEY,
    batch_size=100,
    delay=1.5,
    initial_save_counter=initial_save_counter
)


# ============================================================
# 6. JSON parsing and output
# ============================================================

def clean_json(s: str) -> str:
    s = re.sub(r"^```json\s*", "", str(s))
    return re.sub(r"\s*```$", "", s).strip()


results_df["result_clean"] = results_df["result"].apply(clean_json)

rows = []
for _, r in results_df.iterrows():
    try:
        d = json.loads(r["result_clean"])
        d["DOI"] = r["DOI"]
    except Exception:
        d = {
            "DOI": r["DOI"],
            "Inclusion1": None,
            "Inclusion2": None,
            "Exclusion1": None,
            "Exclusion2": None,
            "Exclusion3": None,
            "Exclusion4": None,
            "Final_decision": "FAILED_TO_PARSE"
        }
    rows.append(d)

final_df = pd.DataFrame(rows)
final_df.to_csv(
    os.path.join(result_dir, "parsed_results_clean_3rd_step.csv"),
    index=False,
    encoding="utf-8-sig"
)

included = final_df[final_df["Final_decision"] == "included"].merge(
    combined_final, on="DOI", how="left"
)
unclear = final_df[final_df["Final_decision"] == "unclear"].merge(
    combined_final, on="DOI", how="left"
)

included.to_csv(
    os.path.join(output_dir, "included_only_3rd_step.csv"),
    index=False,
    encoding="utf-8-sig"
)
unclear.to_csv(
    os.path.join(output_dir, "unclear_only_3rd_step.csv"),
    index=False,
    encoding="utf-8-sig"
)

print("Process completed!")