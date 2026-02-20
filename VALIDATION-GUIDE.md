# MIABIS on FHIR — Validation Guide

## Quick Start

```bash
# 1. Put your JSON bundles in a folder
mkdir bundles
cp *.json bundles/

# 2. Run — validates every .json in the folder
python validate-miabis.py bundles/
```

First run installs SUSHI, clones the IG, downloads the validator (~300 MB). Subsequent runs reuse the cached setup.

## Usage

```bash
# Validate all .json files in a folder
python validate-miabis.py /path/to/folder

# Validate a single file
python validate-miabis.py /path/to/my-bundle.json

# Default: validates all .json in ./bundles/
python validate-miabis.py

# Skip setup (reuse existing IG build + validator) — faster re-runs
python validate-miabis.py --skip-setup bundles/
```

> Works on **Windows**, **macOS**, and **Linux** — no WSL or bash needed.

## Prerequisites

| Tool     | Minimum Version | Check command   | Install from                        |
|----------|----------------|-----------------|-------------------------------------|
| Python   | 3.8+           | `python --version` | https://python.org                |
| Java     | 17+            | `java -version` | https://adoptium.net                |
| Git      | any            | `git --version` | https://git-scm.com                |
| Node.js  | 18+            | `node -v`       | https://nodejs.org                  |

All four must be on your system PATH.

## What the Script Does

1. **Checks prerequisites** — verifies Java, Git, Node.js, npm are available
2. **Installs SUSHI** — the FSH-to-FHIR compiler (`npm install -g fsh-sushi`)
3. **Clones/updates the IG** — always pulls the latest `BBMRI-cz/miabis-on-fhir` from GitHub
4. **Builds with SUSHI** — generates `StructureDefinition` JSON files in `fsh-generated/resources/`
5. **Downloads the HL7 FHIR Validator** — `validator_cli.jar` (~300 MB); re-downloads if older than 30 days
6. **Validates each `.json` file** — checks every resource against its declared MIABIS profile
7. **Produces per-file reports** — HTML + log for each file, plus a summary table

Use `--skip-setup` on subsequent runs to skip steps 1–5 and go straight to validation.

## Output Structure

```
miabis-validation/
├── miabis-on-fhir/          # cloned IG repo (cached)
├── validator_cli.jar         # HL7 validator (cached, refreshed every 30 days)
└── reports/
    ├── validation-summary.txt                    # one-line-per-file table
    ├── miabis-bundle-10donors-validation-report.html
    ├── miabis-bundle-10donors-validation-log.txt
    ├── miabis-bundle-50donors-validation-report.html
    ├── miabis-bundle-50donors-validation-log.txt
    └── ...
```

### Summary file example

```
MIABIS on FHIR — Validation Summary
Date: 2026-02-20 14:30:00 UTC
Files validated: 3
================================================================

FILE                                               ERRORS WARNINGS    NOTES RESULT
----                                               ------  --------   ----- ------
miabis-bundle-10donors.json                             0       12       5 PASS
miabis-bundle-50donors.json                             0       58      25 PASS
miabis-bundle-broken.json                               7        3       2 FAIL

================================================================
TOTALS: 3 files | 2 passed | 1 failed
================================================================
```

## Reading the Output

The validator prints lines like:

```
  Information: All OK (0 errors, 0 warnings, 5 notes)
```

Or if there are issues:

```
  ERROR: Bundle.entry[3].resource (Organization/biobank-CZ-001):
    Profile https://...miabis-biobank, Element 'Organization.partOf':
    minimum required = 1, but only found 0
```

Each issue shows:
- **Severity**: ERROR / WARNING / INFORMATION
- **Location**: which resource and element
- **Rule**: what constraint was violated

### Common warnings (usually safe to ignore)

| Warning | Explanation |
|---------|-------------|
| `extension-Group.member.entity from FHIR version 5.0 is not allowed` | R5 backport extension — declared in the IG profiles, validator may not resolve it without the full IG publisher build |
| `Unable to find a profile match for Organization/...` | Juristic person Organizations have no MIABIS profile (they are plain FHIR Organizations used as `partOf` targets) |
| `This element does not match any known slice` | Informational — the validator found an element that doesn't match a named slice but is allowed by `rules: #open` |

## Generating Test Bundles

Use the companion `generate-miabis-bundle.py` script. Generated files are saved to `bundles/` automatically.

```bash
# Generate bundles of various sizes (output goes to bundles/ by default)
python generate-miabis-bundle.py --donors 10 --seed 1
python generate-miabis-bundle.py --donors 50 --biobanks 3 --collections 5 --seed 2
python generate-miabis-bundle.py --donors 200 --biobanks 5 --collections 10 --seed 3

# Validate all generated bundles
python validate-miabis.py
```

## Manual Validation (without the script)

```bash
# Install SUSHI
npm install -g fsh-sushi

# Clone and build the IG
git clone --depth 1 https://github.com/BBMRI-cz/miabis-on-fhir.git
cd miabis-on-fhir
sushi build
cd ..

# Download the validator
# (or download manually from https://github.com/hapifhir/org.hl7.fhir.core/releases/latest)
curl -L -o validator_cli.jar \
  "https://github.com/hapifhir/org.hl7.fhir.core/releases/latest/download/validator_cli.jar"

# Validate
java -jar validator_cli.jar \
  my-bundle.json \
  -ig miabis-on-fhir/fsh-generated/resources \
  -version 4.0.1 \
  -allow-example-urls true \
  -extension http://example.org/ \
  -output validation-report.html
```

## Profile ID Reference

| Profile Name           | Profile ID (for `meta.profile`)       |
|------------------------|---------------------------------------|
| Biobank                | `miabis-biobank`                      |
| CollectionOrganization | `miabis-collection-organization`      |
| Collection             | `miabis-collection`                   |
| NetworkOrganization    | `miabis-network-organization`         |
| Network                | `miabis-network`                      |
| SampleDonor            | `miabis-sample-donor`                 |
| Sample                 | `miabis-sample`                       |
| MiabisCondition        | `miabis-condition`                    |
| MiabisObservation      | `miabis-observation`                  |

All profile URLs follow the pattern: `https://fhir.bbmri-eric.eu/StructureDefinition/<profile-id>`

## CodeSystem Quick Reference

| CodeSystem ID                          | Used for                        | Example codes                     |
|----------------------------------------|---------------------------------|-----------------------------------|
| `miabis-detailed-samply-type-cs`       | Specimen.type                   | `WholeBlood`, `Plasma`, `DNA`     |
| `miabis-collection-sample-type-cs`     | Collection characteristic       | `Blood`, `TissueFrozen`, `Serum`  |
| `miabis-storage-temperature-cs`        | Storage temperature             | `RT`, `-18to-35`, `-60to-85`, `LN`|
| `miabis-dataset-type-CS`              | Donor dataset type              | `Lifestyle`, `BiologicalSamples`  |
| `miabis-collection-dataset-typeCS`     | Collection dataset type         | `Clinical`, `Genomic`, `Proteomic`|
| `miabis-collection-design-cs`          | Collection design               | `CaseControl`, `CrossSectional`   |
| `miabis-infrastructural-capabilities-cs`| Biobank capabilities           | `SampleStorage`, `DataStorage`, `Biosafety` |
| `miabis-inclusion-criteria-cs`         | Collection inclusion criteria   | `HealthStatus`, `AgeGroup`, `Sex` |
| `miabis-characteristicCS`             | Group characteristic codes      | `Age`, `Sex`, `StorageTemperature`, `MaterialType`, `Diagnosis` |
| `miabis-use-and-access-conditions-cs`  | Collection access conditions    | `CommercialUse`, `Collaboration`  |
| `miabis-sample-source-cs`             | Sample source                   | `Human`, `Animal`, `Environment`  |
