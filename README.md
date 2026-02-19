# MIABIS on FHIR — Transaction Bundle Generator

A Python script that generates realistic, standards-compliant **FHIR R4 transaction bundles** conforming to the [MIABIS on FHIR Implementation Guide](https://fhir.bbmri-eric.eu/) developed by [BBMRI-ERIC](https://www.bbmri-eric.eu/).

## Overview

This tool is designed for **testing, development, and validation** of MIABIS on FHIR endpoints. It produces synthetic biobank datasets that include the full hierarchy of MIABIS resources — from juristic persons and biobanks down to individual donor specimens and observations.

### Generated Resources

| FHIR Resource | MIABIS Concept |
|---|---|
| `Organization` (Juristic Person) | Parent legal entity |
| `Organization` (Biobank) | Biobank facility |
| `Organization` (Network Organization) | Network coordinating entity |
| `Group` (Network) | Biobank network membership |
| `Organization` (Collection Organization) | Collection metadata |
| `Group` (Collection) | Sample collection with characteristics |
| `Patient` | Sample donor |
| `Condition` | ICD-10 diagnosis |
| `Specimen` | Biological sample |
| `DiagnosticReport` | Pathology report |
| `Observation` | Sample-level diagnosis |

## Requirements

- Python 3.8+
- No external dependencies (standard library only)

## Installation

```bash
git clone https://github.com/sthanke/MiabisonFHIR_Generator.git
cd MiabisonFHIR_Generator
```

## Usage

```bash
# Generate a bundle with 10 donors (minimal test dataset)
python generate-miabis-bundle.py --donors 10

# Generate a larger dataset with multiple biobanks and collections
python generate-miabis-bundle.py --donors 50 --biobanks 3 --collections 5

# Specify output file and use a fixed seed for reproducibility
python generate-miabis-bundle.py --donors 100 --output large-bundle.json --seed 42
```

### Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `--donors` | ✅ Yes | — | Number of sample donors to generate |
| `--biobanks` | No | `1` | Number of biobanks |
| `--collections` | No | `1` | Number of collections |
| `--output` | No | `miabis-bundle-<N>donors.json` | Output file path |
| `--seed` | No | random | Random seed for reproducibility |

## Example Output

Running the script creates a FHIR transaction bundle JSON file. For 10 donors the bundle typically contains:

- 2× Organization (juristic person + biobank)
- 1× Organization (network org) + 1× Group (network)
- 1× Organization (collection org) + 1× Group (collection)
- 10× Patient (donors)
- 10× Condition
- 10–30× Specimen
- 10× DiagnosticReport
- 10–30× Observation

A [sample output file](miabis-bundle-10donors.json) for 10 donors is included in this repository.

## Validation

Validate generated bundles using the [FHIR Validator CLI](https://confluence.hl7.org/display/FHIR/Using+the+FHIR+Validator):

```bash
java -jar validator_cli.jar miabis-bundle-10donors.json \
    -ig miabis-on-fhir/fsh-generated/resources \
    -version 4.0.1 -allow-example-urls true \
    -extension http://example.org/
```

## MIABIS on FHIR Resources

- 📄 [MIABIS on FHIR IG](https://fhir.bbmri-eric.eu/)
- 🏛️ [BBMRI-ERIC](https://www.bbmri-eric.eu/)
- 📦 [BBMRI-ERIC Directory](https://directory.bbmri-eric.eu/)

## License

This project is released under the [MIT License](LICENSE).

## Author

Developed by [Sten Hanke](https://github.com/sthanke) for BBMRI-ERIC.
