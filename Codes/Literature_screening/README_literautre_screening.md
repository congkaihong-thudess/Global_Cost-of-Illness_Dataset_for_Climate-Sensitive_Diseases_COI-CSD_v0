# Literature Screening

## Method

Three-step LLM-powered screening to identify peer-reviewed studies reporting actual incurred costs for climate-sensitive diseases (CSDs):

- **Step 1**: Identify records explicitly mentioning ≥1 CSD (80+ diseases, see `Supplementary_materials/Supplementary_information_v0.pdf`)
- **Step 2**: Retain records quantifying disease costs/expenditures
- **Step 3**: Filter for actual incurred costs (direct/indirect); exclude modeled projections, cost gaps, or unit prices

Each abstract is independently screened three times per step; records passing ≥2 of 3 rounds proceed. Please refer to the Methods 4.3 of main article.

## Code Files

(R version)
| File | Description |
|---|---|
| `screen_01_diseases.r` | Step 1 |
| `screen_02_economic.r` | Step 2 |
| `screen_03_actual.r` | Step 3 |

(Python version)
| File | Description |
|---|---|
| `screen_01_diseases.py` | Step 1 |
| `screen_02_economic.py` | Step 2 |
| `screen_03_actual.py` | Step 3 |

## Required Packages

- **For R version**: "dplyr","purrr","stringr","readr","readxl","tidyr","httr","jsonlite","glue"
- **For Python version**: "requests","pandas","openpyxl"

## Input / Output

### Input

| File | Format | Step |
|---|---|---|
| `original_literature_*.xls` | XLS | Step 1 input |
| `literature_after_1st_step_*.xls` | XLS | Step 2 input |
| `literature_after_2nd_step_*.xls` | XLS | Step 3 input |

### Output

| File | Format | Step |
|---|---|---|
| `included_only_1st_step.csv` | CSV | Step 1 output 1 |
| `unclear_only_1st_step.csv` | CSV | Step 1 output 2 |
| `included_only_2nd_step.csv` | CSV | Step 2 output 1 |
| `unclear_only_2nd_step.csv` | CSV | Step 2 output 2 |
| `included_only_3rd_step.csv` | CSV | Step 3 output 1 |
| `unclear_only_3rd_step.csv` | CSV | Step 3 output 2 |

### Final Output

`included_only_3rd_step.csv`

Strongly recommend running each screening step at least three times and conducting comprehensive voting to select the literature that passes the screening,
in order to improve the robustness of the screening.
