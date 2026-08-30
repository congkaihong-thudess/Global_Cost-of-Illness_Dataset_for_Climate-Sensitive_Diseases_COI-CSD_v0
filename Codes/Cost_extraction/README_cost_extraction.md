# Cost Data Extraction

## Method

Four-step LLM-powered pipeline to extract cost values and associated metadata from full-text articles. Please refer to Methods 4.4 of main article for details。

- **Step 1**: Extract cost tables/paragraphs from full text (inclusion: cost keywords + currency symbols; exclusion: unit prices, cost changes, benefit-cost ratios)
- **Step 2**: Extract key information paragraphs (Methods, Baseline results, and sections adjacent to cost tables) for six groups: year/region, inflation/base year, population characteristics, disease name/code, cost categories, statistical caliber/sample size
- **Step 3**: Identify individual cost values from tables, traversing top-left to bottom-right; extract associated category information (headers, footnotes)
- **Step 4 (4 sub-steps)**: Populate complete extraction template:
  - Sub-step 1: Basic cost info (year, country, disease name, cost value)
  - Sub-step 2: Population characteristics (age, gender, income)
  - Sub-step 3: Cost categories (statistical caliber, sample size, reimbursement type, treatment type)
  - Sub-step 4: Categorical inference (harmonized insurance/treatment types)
- **Data Value Review**: Verify extracted values for quantity unit errors (thousand, million, billion misclassification; see手稿 Methods 4.6 first paragraph)

## Code Files

| File | Description |
|---|---|
| `extract_01_table.py` | Extract cost tables/paragraphs from full text |
| `extract_02_paragraphs.py` | Extract key information paragraphs for six groups |
| `extract_03_value.py` | Identify individual cost values and category info from tables |
| `step4_populate_fields/` | Folder containing four sub-steps of inferring and harmonizing cost classification information |
| `step4_populate_fields/extract_04_final_4.1.py` | Fill year, country, disease name, cost value |
| `step4_populate_fields/extract_04_final_4.2.py` | Fill age, gender, income level |
| `step4_populate_fields/extract_04_final_4.3.py` | Fill statistical caliber, sample size, reimbursement, treatment |
| `step4_populate_fields/extract_04_final_4.4.py` | Harmonize insurance and treatment types |
| `check_megnitude.py` | Review and correct thousand/million/billion unit errors |

## Required Packages
