# 🌍 Global Cost-of-Illness Dataset for Climate-Sensitive Diseases (COI-CSD)

[![DOI](https://img.shields.io/badge/DOI-pending-red)](https://doi.org/)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC_BY_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

> A harmonized global dataset of 27,489 cost observations across 80+ climate-sensitive diseases, extracted from 890+ peer-reviewed publications (2015–2025) via LLM-assisted automated literature mining.

---

## 📌 Overview

As climate change intensifies, the health burden of extreme weather events has grown substantially. However, most health economic assessments rely on abstract welfare metrics like the value of a statistical life (VSL), which have no counterpart in real economic accounts. **Cost-of-illness (COI)** offers a tangible alternative—capturing directly observable economic costs that can inform evidence-based climate health policy.

This repository provides the **first harmonized global COI dataset for climate-sensitive diseases (CSDs)** . It contains **27,489 cost observations** extracted from **890+ peer-reviewed publications** published between January 2015 and July 2025, spanning **94 countries** and **80+ CSDs**. All values are standardized to **2024 USD**, mapped to **Global Burden of Disease (GBD)** hierarchies, and annotated with a **three-tier confidence framework** (Evidence, Agreement, Credibility).

The dataset supports:
- Cross-country cost comparisons
- Climate-health economic modeling
- Evidence-based policy design and resource allocation
- Quantification of health co-benefits of climate action

---

## 📖 Methodological Overview

We applied a five-step pipeline to build this dataset:

1. **Systematic Literature Search** – Searched PubMed, Scopus, and Web of Science for peer-reviewed literature on CSD costs (2015–2025).
2. **LLM-Powered Literature Screening** – Used DeepSeek-V3.2 to identify studies reporting actual incurred costs for CSDs, with three independent assessments per record.
3. **LLM-Assisted Cost Extraction** – Extracted cost values and associated metadata from full texts via a structured pipeline (cost tables → key paragraphs → value identification → information inference and classification).
4. **Harmonization** – Standardized disease names to GBD hierarchies, unified statistical calibers (per patient per year / per incident), categorized insurance and treatment types per SHA and NHA frameworks, and converted all values to constant 2024 USD using World Bank CPI and exchange rates.
5. **Confidence Scoring** – Applied a three-tier confidence framework (Evidence, Agreement, Credibility) adapted from IPCC to each type of cost, enabling transparent quality assessment.

![Research Flow](Supplementary_materials/Figures/Figure_5_compress.jpg)

*Figure: Overview of the research pipeline (manuscript Figure 5).*

For detailed methodology, see the [manuscript](#citation) and the code READMEs in each step folder.

---

## 📂 Repository Contents




### Key Components

| Component | Description |
|-----------|-------------|
| **Full Dataset** | Main dataset from literature extraction, and official reported cost dataset from several countries. |
| **Extraction Code** | Complete Python (or R) pipeline with prompts and configuration. |
| **Supplementary Materials** | Figures in manuscrpit, CSD lists, search keywords, all LLM prompts, quality assessment results. |

See the README in each code/ subfolder for detailed instructions.

---

## 📋 Data Dictionary
The main dataset includes 32 fields organized into five clusters. Key fields include:
| Field | Description |
|-------|-------------|
| data_country	| Country of the cost |
| data_year | Year of the cost |
| cost_usd_2024_unified |	Cost per patient per year or per incident, converted to 2024 USD |
| disease_name_infer	| Harmonized GBD2021 Non Fatal ICD Code Map Level 3 disease name |
| population_age | Age group of population related to the cost |
| cost_caliber_unified	| Standardized statistical caliber |
| cost_insurance_infer	| Harmonized insurance type (SHA) |
| cost_treatment_infer	| Harmonized treatment type (NHA) |
| literature_doi | DOI of the literature |

For the complete field list and definitions, see data/data_dictionary.csv or manuscript Table 1.

---

## 📝 Citation
If you use this dataset or code in your research, please cite the manuscript:

> Hong, C. et al. A global dataset of cost-of-illness for climate-sensitive diseases through automated literature extraction. [Pending] (2026).
> [URL]

---

## 🙏 Acknowledgments
This research is funded by the National Natural Science Foundation of China (No. 72403022) and the Fundamental and Interdisciplinary Disciplines Breakthrough Plan of the Ministry of Education of China (No. JYB2025XDXM905). 

We appreciate Yang Yang (School of Nursing, Peking University) for curating the research data. 

We thank the developers of DeepSeek, PubMed, Scopus, and Web of Science for providing the infrastructure enabling this research. We also acknowledge the global research community whose primary COI studies made this dataset possible.

---

## 🤝 Contributing
**We welcome contributions!** Please see CONTRIBUTING.md for guidelines. You can:
- Submit new COI estimates from recent publications;
- Report data errors or suggest corrections;
- Improve extraction prompts or harmonization logic;
- Extend the dataset to underrepresented regions or diseases;
.....

---

## 📧 Contact
For questions, please open a GitHub Issue or contact the first author & the corresponding author:
- First author: Congkai Hong, hck24@mails.tsinghua.edu.cn, Department of Earth System Science, Tsinghua University
- Corresponding author: Wenjia Cai, wcai@tsinghua.edu.cn, Department of Earth System Science, Tsinghua University
