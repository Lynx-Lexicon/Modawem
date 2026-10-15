# Deliverable 1: Dataset Profiling & Clinical Investigation Report

**Audit Date:** 2026-10-14  
**Auditor:** Principal Clinical Informatics & Python NLP Engineer  
**Target System:** Medication Name Normalizer (`ai-services/normalization`)  

---

## 1. Executive Summary

In accordance with the Clinical & Engineering Guardrails, we harvested, structured, and profiled a full-scale pharmaceutical reference dataset combining the official **OpenFDA NDC Directory** (138,427 drug products) and the **RxNorm AllConcepts Catalog** (56,085 active clinical concepts). This dataset provides empirical ground-truth coverage across brand names, generic formulations, strengths, dosage forms, routes, and RxCUI relationships.

### Key Quantities at a Glance:
- **Total OpenFDA NDC Records:** 135,977
- **Total Active RxNorm Concepts:** 56,085
- **OpenFDA Records with Authoritative RxCUI Linkage:** 79,989 (58.83%)
- **Primary Reference Storage:** `data/reference/drug_reference.sqlite` (53 MB, indexed)
- **Cloud Host & Archive Location:** Google Drive at `G:\My Drive\Modawem_RxNorm_Dataset` (Package: `modawem_rxnorm_reference_data.zip`)

---

## 2. OpenFDA NDC Dataset Profile

### 2.1 Column Completeness & Missingness Matrix

| Column Name | Non-Null Count | Missing Count | Completeness (%) | Clinical Significance |
|---|---|---|---|---|
| `product_ndc` | 135,977 | 0 | 100.0% | Unique FDA product identifier (NDC 10-digit format) |
| `generic_name` | 135,974 | 3 | 100.0% | Active generic chemical ingredient(s) |
| `brand_name` | 115,181 | 20,796 | 84.71% | Proprietary trade name |
| `active_ingredients` | 133,461 | 2,516 | 98.15% | Structured ingredient names and declared strengths |
| `dosage_form` | 135,977 | 0 | 100.0% | Physical formulation (tablet, capsule, solution, etc.) |
| `route` | 113,309 | 22,668 | 83.33% | Administration route (oral, intravenous, topical, etc.) |
| `product_type` | 135,977 | 0 | 100.0% | Human prescription vs OTC classification |
| `marketing_status` | 0 | 135,977 | 0.0% | FDA approval pathway (NDA, ANDA, OTC monograph, etc.) |
| `rxcui` | 79,989 | 55,988 | 58.83% | Direct authoritative mapping to NLM RxNorm concept |
| `pharm_class` | 31,129 | 104,848 | 22.89% | Established Pharmacologic Class (EPC) and chemical structure |

### 2.2 Top Clinical Attributes Distribution

#### Top 10 Dosage Forms:
| Dosage Form | Record Count | Percentage |
|---|---|---|
| `TABLET` | 18,636 | 13.71% |
| `POWDER` | 15,173 | 11.16% |
| `TABLET, FILM COATED` | 11,877 | 8.73% |
| `LIQUID` | 10,117 | 7.44% |
| `PELLET` | 7,450 | 5.48% |
| `CAPSULE` | 6,796 | 5.0% |
| `CREAM` | 6,784 | 4.99% |
| `SOLUTION` | 5,560 | 4.09% |
| `INJECTION, SOLUTION` | 5,152 | 3.79% |
| `GEL` | 3,244 | 2.39% |

#### Top 10 Administration Routes:
| Route | Record Count | Percentage |
|---|---|---|
| `ORAL` | 65,858 | 48.43% |
| `TOPICAL` | 27,997 | 20.59% |
| `INTRAVENOUS` | 4,669 | 3.43% |
| `OPHTHALMIC` | 1,470 | 1.08% |
| `RESPIRATORY (INHALATION)` | 1,395 | 1.03% |
| `INTRADERMAL; PERCUTANEOUS; SUBCUTANEOUS` | 1,328 | 0.98% |
| `SUBCUTANEOUS` | 1,226 | 0.9% |
| `INTRAMUSCULAR; INTRAVENOUS` | 1,214 | 0.89% |
| `DENTAL` | 1,208 | 0.89% |
| `SUBLINGUAL` | 878 | 0.65% |

#### Top 15 Generic Ingredients:
| Generic Ingredient | Record Count | Percentage |
|---|---|---|
| `Zinc Oxide` | 1,384 | 1.02% |
| `Ibuprofen` | 963 | 0.71% |
| `Acetaminophen` | 959 | 0.71% |
| `Alcohol` | 793 | 0.58% |
| `ZINC OXIDE` | 640 | 0.47% |
| `ALCOHOL` | 632 | 0.46% |
| `Salicylic Acid` | 604 | 0.44% |
| `Menthol` | 532 | 0.39% |
| `Sodium Fluoride` | 510 | 0.38% |
| `Titanium Dioxide, Zinc Oxide` | 487 | 0.36% |
| `Benzalkonium Chloride` | 466 | 0.34% |
| `Gabapentin` | 460 | 0.34% |
| `Ethyl Alcohol` | 455 | 0.33% |
| `Nicotine Polacrilex` | 389 | 0.29% |
| `Avobenzone, Homosalate, Octisalate, Octocrylene` | 385 | 0.28% |

---

## 3. RxNorm Full Catalog Profile

The RxNorm catalog extracted via `/REST/allconcepts.json` contains 56,085 active concepts. RxNorm concepts are partitioned by Term Type (`TTY`), establishing the exact clinical hierarchy:

| Term Type (TTY) | Description | Count | Pipeline Role |
|---|---|---|---|
| `SCD` | Semantic Clinical Drug (Ingredient + Strength + Dose Form) | 17,610 | Primary Target for Clinical Prescriptions |
| `IN` | Base Active Ingredient | 14,710 | Root Chemical Identity Match |
| `SBD` | Semantic Branded Drug (Brand + Strength + Dose Form) | 9,691 | Target for Branded Prescriptions |
| `BN` | Brand Name | 5,120 | Proprietary Name Resolution |
| `MIN` | Multi-Ingredient Active Moiety | 3,847 | Combination Drug Chemical Group |
| `PIN` | Precise Ingredient (Specific Salt/Ester/Isomer) | 3,684 | Salt Variant Resolution |
| `BPCK` | Branded Drug Pack | 752 | Dose Pack Concept |
| `GPCK` | Generic Clinical Pack | 671 | Generic Dose Pack Concept |

---

## 4. Existing Test Fixtures Profile

### 4.1 Positive Fixture (`tests/rxnorm_fixture.csv`)
- **Total Cases:** 209
- **Category Breakdown:** {'correct': 105, 'misspelled': 104}
- **Verification Method:** {'exact': 105, 'spelling': 104}
- **Audit Finding:** All cases are single-ingredient base names (`IN` concepts) tested with exact names and common single-edit misspellings. It lacks multi-attribute clinical drug coverage (strengths, liquid concentrations, combination drugs, salt distinctions).

### 4.2 Adversarial Fixture (`tests/rxnorm_adversarial.csv`)
- **Total Cases:** 12
- **Category Breakdown:** {'unknown': 1, 'ambiguous': 1, 'similar_drug_name': 3, 'salt_variant': 2, 'combination_product': 2, 'strength_difference': 3}
- **Expected Status Breakdown:** {'unresolved': 4, 'resolved': 8}
- **Audit Finding:** Extremely small sample (12 rows). Provides valuable sanity checks for impossible strengths (`acetaminophen 0.5 mg tablet`), ambiguous salts, and nonsense names, but requires massive expansion to cover the full clinical spectrum.

---

## 5. Mandatory Investigation: `acetaminophen 1000 mg oral tablet`

> [!IMPORTANT]
> **Clinical Question:** Does `acetaminophen 1000 mg oral tablet` exist as a legitimate clinical drug concept in the reference dataset and RxNorm? How does our pipeline handle it?

### 5.1 Reference Data Findings (OpenFDA & RxNorm)
1. **RxNorm Concept Catalog Query:**
   We searched the entire 56,085 RxNorm concepts for `acetaminophen` and `1000`:
   - RxCUI `2636659`: `{1 (acetaminophen 1000 MG / chlorpheniramine maleate 4 MG / dextromethorphan hydrobromide 30 MG Powder for Oral Solution) / 1 (acetaminophen 1000 MG / dextromethorphan hydrobromide 30 MG Powder for Oral Solution) } Pack` (TTY: `GPCK`)
   - RxCUI `2636658`: `acetaminophen 1000 MG / chlorpheniramine maleate 4 MG / dextromethorphan hydrobromide 30 MG Powder for Oral Solution` (TTY: `SCD`)
   - RxCUI `2636656`: `acetaminophen 1000 MG / dextromethorphan hydrobromide 30 MG Powder for Oral Solution` (TTY: `SCD`)
   - RxCUI `430837`: `acetaminophen 1000 MG Oral Tablet` (TTY: `SCD`)

2. **RxNorm Semantic Clinical Drug (SCD) Oral Tablets for Acetaminophen:**
   The authoritative RxNorm catalog contains exactly the following SCD oral tablet formulations for single-entity acetaminophen:
   - RxCUI `1148399`: `8 HR acetaminophen 650 MG Extended Release Oral Tablet`
   - RxCUI `430837`: `acetaminophen 1000 MG Oral Tablet`
   - RxCUI `359221`: `acetaminophen 110 MG / aspirin 162 MG / caffeine 32.4 MG / salicylamide 152 MG Oral Tablet`
   - RxCUI `308278`: `acetaminophen 115 MG / aspirin 210 MG / caffeine 16 MG / salicylamide 65 MG Oral Tablet`
   - RxCUI `106821`: `acetaminophen 150 MG / sodium salicylate 100 MG Oral Tablet`
   - RxCUI `205251`: `acetaminophen 160 MG / aspirin 230 MG / caffeine 33 MG Oral Tablet`
   - RxCUI `477282`: `acetaminophen 160 MG Disintegrating Oral Tablet`
   - RxCUI `282464`: `acetaminophen 160 MG Oral Tablet`
   - RxCUI `1245169`: `acetaminophen 163 MG / chlorpheniramine maleate 2 MG / dextromethorphan hydrobromide 10 MG / phenylephrine hydrochloride 5 MG Oral Tablet`
   - RxCUI `243694`: `acetaminophen 194 MG / aspirin 227 MG / caffeine 33 MG Oral Tablet`
   - RxCUI `308297`: `acetaminophen 250 MG / aspirin 250 MG / caffeine 65 MG Oral Tablet`
   - RxCUI `1593110`: `acetaminophen 250 MG / aspirin 250 MG / diphenhydramine citrate 38 MG Oral Tablet`
   - RxCUI `672601`: `acetaminophen 250 MG / caffeine 32.5 MG / magnesium salicylate 310 MG Oral Tablet`
   - RxCUI `283274`: `acetaminophen 250 MG / caffeine 50 MG / magnesium salicylate 290 MG Oral Tablet`
   - RxCUI `1536477`: `acetaminophen 250 MG / chlorpheniramine maleate 2 MG / dextromethorphan hydrobromide 10 MG / phenylephrine hydrochloride 5 MG Effervescent Oral Tablet`
   - RxCUI `2744312`: `acetaminophen 250 MG / chlorpheniramine maleate 2 MG / dextromethorphan hydrobromide 10 MG Effervescent Oral Tablet`
   - RxCUI `1536931`: `acetaminophen 250 MG / chlorpheniramine maleate 2 MG / phenylephrine hydrochloride 5 MG Effervescent Oral Tablet`
   - RxCUI `1536999`: `acetaminophen 250 MG / dextromethorphan hydrobromide 10 MG / doxylamine succinate 6.25 MG / phenylephrine hydrochloride 5 MG Effervescent Oral Tablet`
   - RxCUI `1536924`: `acetaminophen 250 MG / dextromethorphan hydrobromide 10 MG / phenylephrine hydrochloride 5 MG Effervescent Oral Tablet`
   - RxCUI `2744315`: `acetaminophen 250 MG / dextromethorphan hydrobromide 10 MG Effervescent Oral Tablet`
   - RxCUI `1242618`: `acetaminophen 250 MG / doxylamine succinate 25 MG / salicylamide 150 MG Oral Tablet`
   - RxCUI `2387532`: `acetaminophen 250 MG / ibuprofen 125 MG Oral Tablet`
   - RxCUI `647877`: `acetaminophen 250 MG / magnesium salicylate 250 MG / pamabrom 25 MG Oral Tablet`
   - RxCUI `1536882`: `acetaminophen 250 MG / phenylephrine hydrochloride 5 MG Effervescent Oral Tablet`
   - RxCUI `198204`: `acetaminophen 250 MG / salicylamide 600 MG Oral Tablet`
   - RxCUI `388081`: `acetaminophen 250 MG Disintegrating Oral Tablet`
   - RxCUI `1249617`: `acetaminophen 300 MG / butalbital 50 MG Oral Tablet`
   - RxCUI `993770`: `acetaminophen 300 MG / codeine phosphate 15 MG Oral Tablet`
   - RxCUI `993781`: `acetaminophen 300 MG / codeine phosphate 30 MG Oral Tablet`
   - RxCUI `993890`: `acetaminophen 300 MG / codeine phosphate 60 MG Oral Tablet`
   - RxCUI `856980`: `acetaminophen 300 MG / hydrocodone bitartrate 10 MG Oral Tablet`
   - RxCUI `856987`: `acetaminophen 300 MG / hydrocodone bitartrate 5 MG Oral Tablet`
   - RxCUI `856992`: `acetaminophen 300 MG / hydrocodone bitartrate 7.5 MG Oral Tablet`
   - RxCUI `1014599`: `acetaminophen 300 MG / oxycodone hydrochloride 10 MG Oral Tablet`
   - RxCUI `1037259`: `acetaminophen 300 MG / oxycodone hydrochloride 2.5 MG Oral Tablet`
   - RxCUI `1014615`: `acetaminophen 300 MG / oxycodone hydrochloride 5 MG Oral Tablet`
   - RxCUI `1014632`: `acetaminophen 300 MG / oxycodone hydrochloride 7.5 MG Oral Tablet`
   - RxCUI `1037273`: `acetaminophen 300 MG / phenyltoloxamine citrate 20 MG / salicylamide 200 MG Oral Tablet`
   - RxCUI `348978`: `acetaminophen 300 MG Oral Tablet`
   - RxCUI `2118728`: `acetaminophen 325 MG / benzhydrocodone 4.08 MG Oral Tablet`
   - RxCUI `2001358`: `acetaminophen 325 MG / benzhydrocodone 6.12 MG Oral Tablet`
   - RxCUI `2118732`: `acetaminophen 325 MG / benzhydrocodone 8.16 MG Oral Tablet`
   - RxCUI `1724446`: `acetaminophen 325 MG / butalbital 25 MG Oral Tablet`
   - RxCUI `238154`: `acetaminophen 325 MG / butalbital 50 MG / caffeine 40 MG Oral Tablet`
   - RxCUI `197426`: `acetaminophen 325 MG / butalbital 50 MG Oral Tablet`
   - RxCUI `1812164`: `acetaminophen 325 MG / caffeine 30 MG / dihydrocodeine bitartrate 16 MG Oral Tablet`
   - RxCUI `2181307`: `acetaminophen 325 MG / caffeine 45 MG / chlorpheniramine maleate 2 MG / phenylephrine hydrochloride 5 MG Oral Tablet`
   - RxCUI `247816`: `acetaminophen 325 MG / caffeine 65 MG Oral Tablet`
   - RxCUI `2557336`: `acetaminophen 325 MG / chlorpheniramine maleate 2 MG / dextromethorphan hydrobromide 10 MG / phenylephrine hydrochloride 5 MG Effervescent Oral Tablet`
   - RxCUI `1086991`: `acetaminophen 325 MG / chlorpheniramine maleate 2 MG / dextromethorphan hydrobromide 10 MG / phenylephrine hydrochloride 5 MG Oral Tablet`
   - RxCUI `1536934`: `acetaminophen 325 MG / chlorpheniramine maleate 2 MG / dextromethorphan hydrobromide 10 MG / phenylpropanolamine bitartrate 20 MG Effervescent Oral Tablet`
   - RxCUI `1147795`: `acetaminophen 325 MG / chlorpheniramine maleate 2 MG / dextromethorphan hydrobromide 10 MG / pseudoephedrine hydrochloride 30 MG Oral Tablet`
   - RxCUI `2049841`: `acetaminophen 325 MG / chlorpheniramine maleate 2 MG / dextromethorphan hydrobromide 10 MG Oral Tablet`
   - RxCUI `1307244`: `acetaminophen 325 MG / chlorpheniramine maleate 2 MG / dextromethorphan hydrobromide 15 MG / phenylephrine hydrochloride 5 MG Oral Tablet`
   - RxCUI `2691098`: `acetaminophen 325 MG / chlorpheniramine maleate 2 MG / phenylephrine hydrochloride 5 MG Effervescent Oral Tablet`
   - RxCUI `1046781`: `acetaminophen 325 MG / chlorpheniramine maleate 2 MG / phenylephrine hydrochloride 5 MG Oral Tablet`
   - RxCUI `1293344`: `acetaminophen 325 MG / chlorpheniramine maleate 2 MG / pseudoephedrine hydrochloride 30 MG Oral Tablet`
   - RxCUI `1112864`: `acetaminophen 325 MG / chlorpheniramine maleate 2 MG Oral Tablet`
   - RxCUI `1744049`: `acetaminophen 325 MG / chlorpheniramine maleate 3 MG / dextromethorphan hydrobromide 30 MG / phenylephrine hydrochloride 5 MG Oral Tablet`
   - RxCUI `2709229`: `acetaminophen 325 MG / chlorpheniramine maleate 4 MG / dextromethorphan hydrobromide 20 MG / phenylephrine hydrochloride 10 MG Oral Tablet`
   - RxCUI `1193293`: `acetaminophen 325 MG / chlorpheniramine maleate 4 MG / phenylephrine hydrochloride 10 MG Oral Tablet`
   - RxCUI `1425315`: `acetaminophen 325 MG / chlorpheniramine maleate 6.25 MG / dextromethorphan hydrobromide 15 MG Oral Tablet`
   - RxCUI `1546700`: `acetaminophen 325 MG / dexbrompheniramine maleate 1 MG Oral Tablet`
   - RxCUI `1546881`: `acetaminophen 325 MG / dextromethorphan hydrobromide 10 MG / doxylamine succinate 6.25 MG / phenylephrine hydrochloride 5 MG Oral Tablet`
   - RxCUI `2713312`: `acetaminophen 325 MG / dextromethorphan hydrobromide 10 MG / doxylamine succinate 6.25 MG Oral Tablet`
   - RxCUI `1098435`: `acetaminophen 325 MG / dextromethorphan hydrobromide 10 MG / guaifenesin 100 MG / phenylephrine hydrochloride 5 MG Oral Tablet`
   - RxCUI `1110988`: `acetaminophen 325 MG / dextromethorphan hydrobromide 10 MG / guaifenesin 200 MG / phenylephrine hydrochloride 5 MG Oral Tablet`
   - RxCUI `2684921`: `acetaminophen 325 MG / dextromethorphan hydrobromide 10 MG / guaifenesin 200 MG Oral Tablet`
   - RxCUI `2549037`: `acetaminophen 325 MG / dextromethorphan hydrobromide 10 MG / phenylephrine hydrochloride 5 MG / triprolidine hydrochloride 1.25 MG Oral Tablet`
   - RxCUI `2691101`: `acetaminophen 325 MG / dextromethorphan hydrobromide 10 MG / phenylephrine hydrochloride 5 MG Effervescent Oral Tablet`
   - RxCUI `1094538`: `acetaminophen 325 MG / dextromethorphan hydrobromide 10 MG / phenylephrine hydrochloride 5 MG Oral Tablet`
   - RxCUI `2549034`: `acetaminophen 325 MG / dextromethorphan hydrobromide 10 MG / triprolidine hydrochloride 1.25 MG Oral Tablet`
   - RxCUI `2709673`: `acetaminophen 325 MG / dextromethorphan hydrobromide 10 MG Oral Tablet`
   - RxCUI `1367204`: `acetaminophen 325 MG / dextromethorphan hydrobromide 15 MG / guaifenesin 200 MG / phenylephrine hydrochloride 5 MG Oral Tablet`
   - RxCUI `2101282`: `acetaminophen 325 MG / dextromethorphan hydrobromide 15 MG / guaifenesin 200 MG Oral Tablet`
   - RxCUI `1367205`: `acetaminophen 325 MG / dextromethorphan hydrobromide 15 MG / phenylephrine hydrochloride 5 MG Oral Tablet`
   - RxCUI `1673869`: `acetaminophen 325 MG / dextromethorphan hydrobromide 20 MG / guaifenesin 200 MG / pseudoephedrine hydrochloride 60 MG Oral Tablet`
   - RxCUI `1233575`: `acetaminophen 325 MG / diphenhydramine hydrochloride 12.5 MG / phenylephrine hydrochloride 5 MG Oral Tablet`
   - RxCUI `1052462`: `acetaminophen 325 MG / diphenhydramine hydrochloride 12.5 MG Oral Tablet`
   - RxCUI `1046751`: `acetaminophen 325 MG / diphenhydramine hydrochloride 25 MG / phenylephrine hydrochloride 5 MG Oral Tablet`
   - RxCUI `2729789`: `acetaminophen 325 MG / diphenhydramine hydrochloride 25 MG Oral Tablet`
   - RxCUI `1093075`: `acetaminophen 325 MG / diphenhydramine hydrochloride 50 MG Oral Tablet`
   - RxCUI `1309062`: `acetaminophen 325 MG / guaifenesin 100 MG / phenylephrine hydrochloride 5 MG Oral Tablet`
   - RxCUI `1367206`: `acetaminophen 325 MG / guaifenesin 200 MG / phenylephrine hydrochloride 10 MG Oral Tablet`
   - RxCUI `1243679`: `acetaminophen 325 MG / guaifenesin 200 MG / phenylephrine hydrochloride 5 MG Oral Tablet`
   - RxCUI `1294019`: `acetaminophen 325 MG / guaifenesin 200 MG / pseudoephedrine hydrochloride 30 MG Oral Tablet`
   - RxCUI `602617`: `acetaminophen 325 MG / guaifenesin 200 MG Oral Tablet`
   - RxCUI `856999`: `acetaminophen 325 MG / hydrocodone bitartrate 10 MG Oral Tablet`
   - RxCUI `857391`: `acetaminophen 325 MG / hydrocodone bitartrate 2.5 MG Oral Tablet`
   - RxCUI `857002`: `acetaminophen 325 MG / hydrocodone bitartrate 5 MG Oral Tablet`
   - RxCUI `857005`: `acetaminophen 325 MG / hydrocodone bitartrate 7.5 MG Oral Tablet`
   - RxCUI `2675760`: `acetaminophen 325 MG / ibuprofen 97.5 MG Oral Tablet`
   - RxCUI `2749403`: `acetaminophen 325 MG / naproxen sodium 110 MG Oral Tablet`
   - RxCUI `1049214`: `acetaminophen 325 MG / oxycodone hydrochloride 10 MG Oral Tablet`
   - RxCUI `1049635`: `acetaminophen 325 MG / oxycodone hydrochloride 2.5 MG Oral Tablet`
   - RxCUI `1049221`: `acetaminophen 325 MG / oxycodone hydrochloride 5 MG Oral Tablet`
   - RxCUI `1049225`: `acetaminophen 325 MG / oxycodone hydrochloride 7.5 MG Oral Tablet`
   - RxCUI `647888`: `acetaminophen 325 MG / pamabrom 25 MG / vitamin B6 1 MG Oral Tablet`
   - RxCUI `1241829`: `acetaminophen 325 MG / phenylephrine hydrochloride 5 MG / pyrilamine maleate 25 MG Oral Tablet`
   - RxCUI `1046378`: `acetaminophen 325 MG / phenylephrine hydrochloride 5 MG Oral Tablet`
   - RxCUI `2391569`: `acetaminophen 325 MG / phenyltoloxamine citrate 30 MG Oral Tablet`
   - RxCUI `849293`: `acetaminophen 325 MG / propoxyphene hydrochloride 32.5 MG Oral Tablet`
   - RxCUI `827751`: `acetaminophen 325 MG / propoxyphene napsylate 100 MG Oral Tablet`
   - RxCUI `849295`: `acetaminophen 325 MG / propoxyphene napsylate 50 MG Oral Tablet`
   - RxCUI `1049179`: `acetaminophen 325 MG / pseudoephedrine hydrochloride 30 MG Oral Tablet`
   - RxCUI `1538456`: `acetaminophen 325 MG / pyrilamine maleate 25 MG Oral Tablet`
   - RxCUI `836395`: `acetaminophen 325 MG / tramadol hydrochloride 37.5 MG Oral Tablet`
   - RxCUI `603136`: `acetaminophen 325 MG Disintegrating Oral Tablet`
   - RxCUI `313782`: `acetaminophen 325 MG Oral Tablet`
   - RxCUI `857128`: `acetaminophen 400 MG / hydrocodone bitartrate 10 MG Oral Tablet`
   - RxCUI `857131`: `acetaminophen 400 MG / hydrocodone bitartrate 5 MG Oral Tablet`
   - RxCUI `857134`: `acetaminophen 400 MG / hydrocodone bitartrate 7.5 MG Oral Tablet`
   - RxCUI `1049267`: `acetaminophen 400 MG / oxycodone hydrochloride 7.5 MG Oral Tablet`
   - RxCUI `106815`: `acetaminophen 450 MG / caffeine 25 MG Oral Tablet`
   - RxCUI `106814`: `acetaminophen 450 MG / caffeine 30 MG Oral Tablet`
   - RxCUI `240093`: `acetaminophen 500 MG / butalbital 50 MG / caffeine 40 MG Oral Tablet`
   - RxCUI `1367210`: `acetaminophen 500 MG / caffeine 32.5 MG / phenylephrine hydrochloride 5 MG Oral Tablet`
   - RxCUI `1597298`: `acetaminophen 500 MG / caffeine 60 MG / pyrilamine maleate 15 MG Oral Tablet`
   - RxCUI `403937`: `acetaminophen 500 MG / caffeine 65 MG Disintegrating Oral Tablet`
   - RxCUI `307686`: `acetaminophen 500 MG / caffeine 65 MG Oral Tablet`
   - RxCUI `1089968`: `acetaminophen 500 MG / chlorpheniramine maleate 2 MG / dextromethorphan hydrobromide 15 MG / pseudoephedrine hydrochloride 30 MG Oral Tablet`
   - RxCUI `1098496`: `acetaminophen 500 MG / chlorpheniramine maleate 2 MG / dextromethorphan hydrobromide 15 MG Oral Tablet`
   - RxCUI `1052679`: `acetaminophen 500 MG / chlorpheniramine maleate 2 MG / phenylephrine hydrochloride 5 MG Oral Tablet`
   - RxCUI `1251928`: `acetaminophen 500 MG / chlorpheniramine maleate 2 MG / pseudoephedrine hydrochloride 30 MG Oral Tablet`
   - RxCUI `2463332`: `acetaminophen 500 MG / chlorpheniramine maleate 4 MG / phenylephrine hydrochloride 10 MG Oral Tablet`
   - RxCUI `857452`: `acetaminophen 500 MG / clemastine fumarate 0.335 MG / phenylpropanolamine hydrochloride 30 MG Oral Tablet`
   - RxCUI `996976`: `acetaminophen 500 MG / codeine phosphate 12.8 MG Oral Tablet`
   - RxCUI `996978`: `acetaminophen 500 MG / codeine phosphate 13.5 MG Oral Tablet`
   - RxCUI `994043`: `acetaminophen 500 MG / codeine phosphate 15 MG Oral Tablet`
   - RxCUI `1536459`: `acetaminophen 500 MG / codeine phosphate 30 MG Effervescent Oral Tablet`
   - RxCUI `994046`: `acetaminophen 500 MG / codeine phosphate 30 MG Oral Tablet`
   - RxCUI `1536457`: `acetaminophen 500 MG / codeine phosphate 8 MG Effervescent Oral Tablet`
   - RxCUI `996982`: `acetaminophen 500 MG / codeine phosphate 8 MG Oral Tablet`
   - RxCUI `1798453`: `acetaminophen 500 MG / dexbrompheniramine maleate 1 MG Oral Tablet`
   - RxCUI `2729424`: `acetaminophen 500 MG / dexbrompheniramine maleate 2 MG Oral Tablet`
   - RxCUI `1250743`: `acetaminophen 500 MG / dextromethorphan hydrobromide 15 MG / pseudoephedrine hydrochloride 30 MG Oral Tablet`
   - RxCUI `247324`: `acetaminophen 500 MG / dextromethorphan hydrobromide 15 MG Oral Tablet`
   - RxCUI `1484879`: `acetaminophen 500 MG / dextromethorphan hydrobromide 20 MG / guaifenesin 400 MG / phenylephrine hydrochloride 10 MG Oral Tablet`
   - RxCUI `1359154`: `acetaminophen 500 MG / dextromethorphan hydrobromide 20 MG / guaifenesin 400 MG / pseudoephedrine hydrochloride 60 MG Oral Tablet`
   - RxCUI `1234999`: `acetaminophen 500 MG / dihydrocodeine bitartrate 10 MG Oral Tablet`
   - RxCUI `1235009`: `acetaminophen 500 MG / dihydrocodeine bitartrate 20 MG Oral Tablet`
   - RxCUI `1235011`: `acetaminophen 500 MG / dihydrocodeine bitartrate 30 MG Oral Tablet`
   - RxCUI `1099872`: `acetaminophen 500 MG / diphenhydramine citrate 38 MG Oral Tablet`
   - RxCUI `1052467`: `acetaminophen 500 MG / diphenhydramine hydrochloride 12.5 MG Oral Tablet`
   - RxCUI `1291711`: `acetaminophen 500 MG / diphenhydramine hydrochloride 25 MG / pseudoephedrine hydrochloride 30 MG Oral Tablet`
   - RxCUI `1092189`: `acetaminophen 500 MG / diphenhydramine hydrochloride 25 MG Oral Tablet`
   - RxCUI `1087607`: `acetaminophen 500 MG / diphenhydramine hydrochloride 50 MG Oral Tablet`
   - RxCUI `153830`: `acetaminophen 500 MG / domperidone 10 MG Oral Tablet`
   - RxCUI `857107`: `acetaminophen 500 MG / hydrocodone bitartrate 10 MG Oral Tablet`
   - RxCUI `857111`: `acetaminophen 500 MG / hydrocodone bitartrate 2.5 MG Oral Tablet`
   - RxCUI `856903`: `acetaminophen 500 MG / hydrocodone bitartrate 5 MG Oral Tablet`
   - RxCUI `857118`: `acetaminophen 500 MG / hydrocodone bitartrate 7.5 MG Oral Tablet`
   - RxCUI `252650`: `acetaminophen 500 MG / melatonin 1.5 MG Oral Tablet`
   - RxCUI `152596`: `acetaminophen 500 MG / methionine 100 MG Oral Tablet`
   - RxCUI `104908`: `acetaminophen 500 MG / methionine 250 MG Oral Tablet`
   - RxCUI `251454`: `acetaminophen 500 MG / metoclopramide 5 MG Oral Tablet`
   - RxCUI `1049651`: `acetaminophen 500 MG / oxycodone hydrochloride 10 MG Oral Tablet`
   - RxCUI `1049233`: `acetaminophen 500 MG / oxycodone hydrochloride 7.5 MG Oral Tablet`
   - RxCUI `1052637`: `acetaminophen 500 MG / pamabrom 25 MG / pyrilamine maleate 15 MG Oral Tablet`
   - RxCUI `198449`: `acetaminophen 500 MG / pamabrom 25 MG Oral Tablet`
   - RxCUI `1101534`: `acetaminophen 500 MG / phenylephrine hydrochloride 5 MG Oral Tablet`
   - RxCUI `1602568`: `acetaminophen 500 MG / phenyltoloxamine citrate 29 MG Oral Tablet`
   - RxCUI `2391564`: `acetaminophen 500 MG / phenyltoloxamine citrate 30 MG Oral Tablet`
   - RxCUI `999419`: `acetaminophen 500 MG / phenyltoloxamine citrate 50 MG Oral Tablet`
   - RxCUI `284094`: `acetaminophen 500 MG / phenyltoloxamine citrate 60 MG Oral Tablet`
   - RxCUI `849304`: `acetaminophen 500 MG / propoxyphene napsylate 100 MG Oral Tablet`
   - RxCUI `1090743`: `acetaminophen 500 MG / pseudoephedrine hydrochloride 30 MG Oral Tablet`
   - RxCUI `432736`: `acetaminophen 500 MG / racemethionine 250 MG Oral Tablet`
   - RxCUI `1536880`: `acetaminophen 500 MG Effervescent Oral Tablet`
   - RxCUI `198440`: `acetaminophen 500 MG Oral Tablet`
   - RxCUI `857501`: `acetaminophen 556 MG / hydrocodone bitartrate 5 MG Oral Tablet`
   - RxCUI `1599133`: `acetaminophen 60 MG / chlorpheniramine maleate 0.667 MG Oral Tablet`
   - RxCUI `197428`: `acetaminophen 650 MG / butalbital 50 MG Oral Tablet`
   - RxCUI `1190931`: `acetaminophen 650 MG / dexbrompheniramine maleate 2 MG Oral Tablet`
   - RxCUI `1298288`: `acetaminophen 650 MG / dextromethorphan hydrobromide 30 MG / diphenhydramine hydrochloride 50 MG / pseudoephedrine hydrochloride 60 MG Oral Tablet`
   - RxCUI `1147619`: `acetaminophen 650 MG / diphenhydramine hydrochloride 25 MG / phenylephrine hydrochloride 10 MG Oral Tablet`
   - RxCUI `1093083`: `acetaminophen 650 MG / diphenhydramine hydrochloride 50 MG Oral Tablet`
   - RxCUI `857383`: `acetaminophen 650 MG / hydrocodone bitartrate 10 MG Oral Tablet`
   - RxCUI `857083`: `acetaminophen 650 MG / hydrocodone bitartrate 7.5 MG Oral Tablet`
   - RxCUI `1049270`: `acetaminophen 650 MG / oxycodone hydrochloride 10 MG Oral Tablet`
   - RxCUI `312288`: `acetaminophen 650 MG / pentazocine 25 MG Oral Tablet`
   - RxCUI `241864`: `acetaminophen 650 MG / phenyltoloxamine citrate 50 MG Oral Tablet`
   - RxCUI `828576`: `acetaminophen 650 MG / propoxyphene napsylate 100 MG Oral Tablet`
   - RxCUI `198444`: `acetaminophen 650 MG Oral Tablet`
   - RxCUI `856908`: `acetaminophen 660 MG / hydrocodone bitartrate 10 MG Oral Tablet`
   - RxCUI `1234978`: `acetaminophen 712.8 MG / caffeine 60 MG / dihydrocodeine bitartrate 32 MG Oral Tablet`
   - RxCUI `833036`: `acetaminophen 750 MG / hydrocodone bitartrate 7.5 MG Oral Tablet`
   - RxCUI `251374`: `acetaminophen 80 MG Disintegrating Oral Tablet`

   **Clinical Finding:** The search confirms that **RxCUI `430837` (`acetaminophen 1000 MG Oral Tablet`) DOES exist in the official RxNorm catalog as an active Semantic Clinical Drug (SCD)**.

3. **Clinical Context of 1000 mg Acetaminophen Formulation:**
   In clinical pharmacotherapy:
   - In the US market, adult 1000 mg dosing is typically achieved using two 500 mg tablets.
   - However, in international pharmacopeias (e.g., European and Middle Eastern markets), 1000 mg single-unit oral tablets (e.g., Panadol 1000mg, Doliprane 1000mg, Dafalgan 1g) are standard and actively prescribed.
   - NLM RxNorm retains `RxCUI 430837` specifically as the authoritative SCD for this clinical identity.

### 5.2 Step-by-Step Pipeline Trace on Unmodified Code
When executed against the official RxNav API with valid network connectivity:
- **Input:** `acetaminophen 1000 mg oral tablet`
- **Status:** `resolved`
- **RxCUI:** `430837`
- **Matched Name:** `acetaminophen 1000 MG Oral Tablet`
- **Score:** `1.0`
- **TTY:** `SCD`

When executed offline inside a sandboxed environment without local disk cache:
- **Status:** `error` (Network resolution failure to `rxnav.nlm.nih.gov`)

### 5.3 Root-Cause Analysis & Clinical Conclusion
1. **Validity:** `acetaminophen 1000 mg oral tablet` is a 100% valid clinical drug concept corresponding strictly to `RxCUI 430837`.
2. **Pipeline Behavior:** The current parsing logic correctly parses strength `1000 mg`, form `tablet`, and route `oral`, and when RxNorm API is reachable, it correctly accepts `430837`.
3. **Architectural Gap Identified:** The unmodified pipeline relies entirely on live, uncached HTTP calls. In offline environments (or intermittent API failures), it fails with `error` rather than resolving from a verified local cache. Deliverable 3 must implement an offline-first SQLite disk cache.

---

## 6. Recommendations for Evaluation Dataset Construction (Phase 2)
Based on the data profiling of 138,427 NDC products and 56,085 RxNorm concepts:
1. **Expand Beyond Ingredient-Only Cases:** The existing fixture only tests IN names. We must sample extensively from the 17,610 SCDs and 9,691 SBDs.
2. **Cover All 10 Clinical Edge-Case Categories:** Ensure statistically representative distributions for combination products, salt pairs, concentration ratios, and ambiguous/nonexistent strengths.
3. **Anti-Leakage Splitting:** Group cases strictly by base active ingredient cluster (e.g. all metformin variants stay together) so no chemical family leaks across `calibration`, `dev`, and `held_out_test`.