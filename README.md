# MIABIS on FHIR — Transaction Bundle Generator & Validator

Python tools for generating and validating **FHIR R4 transaction bundles** conforming to the [MIABIS on FHIR Implementation Guide](https://fhir.bbmri-eric.eu/) developed by [BBMRI-ERIC](https://www.bbmri-eric.eu/).

## Overview

This project provides two scripts:

1. **`generate-miabis-bundle.py`** — generates synthetic biobank datasets for testing, development, and validation of MIABIS on FHIR endpoints.
2. **`validate-miabis.py`** — validates generated bundles against the latest MIABIS on FHIR IG using the HL7 FHIR Validator.

Generated bundles include the full MIABIS resource hierarchy — from juristic persons and biobanks down to individual donor specimens and observations.

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

- Python 3.8+ (no external dependencies needed for generation)
- For validation: Java 17+, Git, Node.js 18+ (details in [VALIDATION-GUIDE.md](VALIDATION-GUIDE.md))

## Installation

```bash
git clone https://github.com/sthanke/MiabisonFHIR_Generator.git
cd MiabisonFHIR_Generator
```

## Quick Start

```bash
# 1. Generate a bundle (saved to bundles/ by default)
python generate-miabis-bundle.py --donors 10

# 2. Validate it
python validate-miabis.py
```

## Generating Bundles

```bash
python generate-miabis-bundle.py --donors 10
python generate-miabis-bundle.py --donors 50 --biobanks 3 --collections 5
python generate-miabis-bundle.py --donors 100 --output my-bundle.json --seed 42
```

Generated files are saved to the `bundles/` folder by default. Use `--output` to write to a custom path instead.

| Argument | Required | Default | Description |
|---|---|---|---|
| `--donors` | Yes | — | Number of sample donors to generate |
| `--biobanks` | No | `1` | Number of biobanks |
| `--collections` | No | `1` | Number of collections |
| `--output` | No | `bundles/miabis-bundle-<N>donors.json` | Output file path |
| `--seed` | No | random | Random seed for reproducibility |

## Validating Bundles

See [VALIDATION-GUIDE.md](VALIDATION-GUIDE.md) for prerequisites, usage, output format, and troubleshooting.

## Project Structure

```
MiabisonFHIR_Generator/
  generate-miabis-bundle.py   # Bundle generator
  validate-miabis.py          # Batch validation script
  bundles/                    # Generated bundles (default output)
  miabis-validation/          # Created by validator (IG clone, reports)
  VALIDATION-GUIDE.md         # Detailed validation documentation
  README.md
  LICENSE
```

## Resources

- [MIABIS on FHIR IG](https://fhir.bbmri-eric.eu/)
- [BBMRI-ERIC](https://www.bbmri-eric.eu/)
- [BBMRI-ERIC Directory](https://directory.bbmri-eric.eu/)

## License

This project is released under the [MIT License](LICENSE).

## Author

Developed by [Sten Hanke](https://github.com/sthanke) for BBMRI-ERIC.
