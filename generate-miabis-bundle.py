#!/usr/bin/env python3
"""
MIABIS on FHIR — Transaction Bundle Generator

Generates a FHIR transaction bundle conforming to the MIABIS on FHIR IG.
All resources use the canonical base URL https://fhir.bbmri-eric.eu/.

Usage:
    python3 generate-miabis-bundle.py --donors 10
    python3 generate-miabis-bundle.py --donors 50 --output my-bundle.json
    python3 generate-miabis-bundle.py --donors 100 --biobanks 3 --collections 5

The script generates a realistic biobank dataset with:
  - Juristic persons (parent organizations)
  - Biobanks with MIABIS extensions
  - A network linking biobanks
  - Collections with characteristics
  - Sample donors (Patient resources)
  - Conditions (ICD-10 diagnoses)
  - Specimens with storage temperature / body site
  - DiagnosticReports
  - Observations (sample-level diagnosis)

Each donor gets 1 condition, 1-3 specimens, 1 diagnostic report, and 1 observation per specimen.
"""

import argparse
import json
import random
import uuid
from datetime import datetime, timedelta

# ===========================================================================
#  Canonical base URL for the MIABIS on FHIR IG
# ===========================================================================
BASE = "https://fhir.bbmri-eric.eu"

# ===========================================================================
#  Reference data — all codes verified against the built IG
# ===========================================================================

ICD10_CODES = [
    ("C34.1", "Upper lobe, bronchus or lung"),
    ("C34.2", "Middle lobe, bronchus or lung"),
    ("C34.3", "Lower lobe, bronchus or lung"),
    ("C50.9", "Breast, unspecified"),
    ("C50.4", "Upper-outer quadrant of breast"),
    ("C18.0", "Caecum"),
    ("C18.2", "Ascending colon"),
    ("C18.7", "Sigmoid colon"),
    ("C61",   "Malignant neoplasm of prostate"),
    ("C25.0", "Head of pancreas"),
    ("C56",   "Malignant neoplasm of ovary"),
    ("C64",   "Malignant neoplasm of kidney, except renal pelvis"),
    ("C16.0", "Cardia"),
    ("C67.9", "Bladder, unspecified"),
    ("C71.9", "Brain, unspecified"),
    ("C73",   "Malignant neoplasm of thyroid gland"),
    ("C43.5", "Malignant melanoma of trunk"),
    ("C22.0", "Liver cell carcinoma"),
    ("C15.9", "Oesophagus, unspecified"),
    ("C20",   "Malignant neoplasm of rectum"),
]

# CodeSystem: miabis-detailed-samply-type-cs (individual specimen types)
SAMPLE_TYPES = [
    ("TissueFreshFrozen",   "Tissue (fresh frozen)"),
    ("TissueFFPE",          "Tissue (FFPE)"),
    ("Blood",               "Whole blood"),
    ("Plasma",              "Plasma"),
    ("Serum",               "Serum"),
    ("DNA",                 "DNA"),
    ("RNA",                 "RNA"),
    ("BuffyCoat",           "Buffy coat"),
    ("Urine",               "Urine"),
    ("Saliva",              "Saliva"),
    ("CellLineTumor",       "Tumor cell line"),
]

# CodeSystem: miabis-collection-sample-type-cs (collection-level types)
COLLECTION_SAMPLE_TYPES = [
    "TissueFrozen", "TissueFFPE", "Blood", "Plasma", "Serum", "DNA",
    "RNA", "BuffyCoat", "Urine", "Saliva",
]

# CodeSystem: miabis-storage-temperature-cs
STORAGE_TEMPERATURES = [
    ("RT",           "Room temperature"),
    ("2to10",        "2 to 10 degrees Celsius"),
    ("minus18to35",  "-18 to -35 degrees Celsius"),
    ("minus60to85",  "-60 to -85 degrees Celsius"),
    ("LN",           "liquid nitrogen, -150 to -196 degrees Celsius"),
    ("Other",        "Other"),
]

# Typical storage temp per sample type
SAMPLE_STORAGE_MAP = {
    "TissueFreshFrozen": "LN",
    "TissueFFPE":        "RT",
    "Blood":             "minus18to35",
    "Plasma":            "minus60to85",
    "Serum":             "minus60to85",
    "DNA":               "minus18to35",
    "RNA":               "minus60to85",
    "BuffyCoat":         "minus60to85",
    "Urine":             "minus18to35",
    "Saliva":            "2to10",
    "CellLineTumor":     "LN",
}

# SNOMED body sites
BODY_SITES = [
    ("39607008",   "Lung structure"),
    ("76752008",   "Breast structure"),
    ("71854001",   "Colon structure"),
    ("41216001",   "Prostatic structure"),
    ("15776009",   "Pancreatic structure"),
    ("15497006",   "Ovarian structure"),
    ("64033007",   "Kidney structure"),
    ("69695003",   "Stomach structure"),
    ("89837001",   "Urinary bladder structure"),
    ("12738006",   "Brain structure"),
    ("69748006",   "Thyroid structure"),
    ("14016003",   "Skin structure of trunk"),
    ("10200004",   "Liver structure"),
    ("32849002",   "Oesophageal structure"),
    ("34402009",   "Rectum structure"),
]

# Map ICD-10 prefix to typical body site
ICD10_BODYSITE = {
    "C34": "39607008", "C50": "76752008", "C18": "71854001", "C20": "34402009",
    "C61": "41216001", "C25": "15776009", "C56": "15497006", "C64": "64033007",
    "C16": "69695003", "C67": "89837001", "C71": "12738006", "C73": "69748006",
    "C43": "14016003", "C22": "10200004", "C15": "32849002",
}

DATASET_TYPES = [
    "Lifestyle", "BiologicalSamples", "SurveyData", "ImagingData",
    "MedicalRecords", "GenomicData", "PhysiologicalBiochemicalMeasurements",
]

COLLECTION_DESIGNS = [
    "CaseControl", "CrossSectional", "LongitudinalCohort",
    "DiseaseSpecificCohort", "PopulationBasedCohort", "Other",
]

SAMPLE_SOURCES = ["Human"]

USE_ACCESS_CONDITIONS = [
    "CommercialUse", "Collaboration", "SpecificResearchUse",
]

INCLUSION_CRITERIA = [
    "HealthStatus", "HospitalPatient", "AgeRange",
    "FamiliesOfAffectedPersons", "Other",
]

INFRASTRUCTURAL_CAPABILITIES = [
    "SampleStorage", "SampleProcessing", "DataStorage",
    "SampleAnalysis", "SampleShipping",
]

QUALITY_STANDARDS = ["ISO 20387", "ISO 9001", "ISO 15189", "OECD Guidelines"]

FIRST_NAMES_M = ["Jan", "Martin", "Petr", "Milan", "Thomas", "Hans", "Erik", "Lars", "Andrei", "Marco"]
FIRST_NAMES_F = ["Eva", "Jana", "Maria", "Petra", "Anna", "Helga", "Ingrid", "Sofia", "Elena", "Lucia"]
LAST_NAMES = ["Novak", "Svoboda", "Mueller", "Schmidt", "Jensen", "Larsson", "Popov", "Rossi", "Silva", "Patel",
              "Horvat", "Kowalski", "Virtanen", "Dupont", "Garcia", "Fernandez", "Bauer", "Fischer", "Weber", "Wagner"]

COUNTRIES = ["CZ", "DE", "AT", "SE", "FI", "IT", "ES", "FR", "NL", "PL", "SI", "PT", "NO", "DK", "BE"]
CITIES = {
    "CZ": ["Prague", "Brno", "Ostrava"], "DE": ["Berlin", "Munich", "Hannover", "Hamburg"],
    "AT": ["Vienna", "Graz", "Innsbruck"], "SE": ["Stockholm", "Gothenburg", "Uppsala"],
    "FI": ["Helsinki", "Turku", "Tampere"], "IT": ["Rome", "Milan", "Florence"],
    "ES": ["Madrid", "Barcelona", "Valencia"], "FR": ["Paris", "Lyon", "Marseille"],
    "NL": ["Amsterdam", "Rotterdam", "Utrecht"], "PL": ["Warsaw", "Krakow", "Gdansk"],
    "SI": ["Ljubljana", "Maribor"], "PT": ["Lisbon", "Porto"], "NO": ["Oslo", "Bergen"],
    "DK": ["Copenhagen", "Aarhus"], "BE": ["Brussels", "Leuven"],
}

BIOBANK_SUFFIXES = [
    "University Hospital Biobank", "Cancer Research Biobank", "National Biobank",
    "Medical Center Biobank", "Clinical Research Biobank", "Integrated Biobank",
    "Genomics & Tissue Bank", "Translational Research Biobank",
]

COLLECTION_NAMES = [
    "Solid Tumors", "Hematological Malignancies", "Breast Cancer Cohort",
    "Lung Cancer Registry", "Colorectal Cancer Study", "Prostate Cancer Cohort",
    "Pancreatic Cancer Collection", "Rare Tumors Collection",
    "Population Health Study", "Metabolic Diseases Cohort",
    "Cardiovascular Sample Repository", "Neurological Disorders Collection",
]


def narrative(resource_type, resource_id, summary):
    return {
        "status": "generated",
        "div": f'<div xmlns="http://www.w3.org/1999/xhtml"><p><b>{resource_type}/{resource_id}</b>: {summary}</p></div>'
    }


def make_entry(resource):
    rt = resource["resourceType"]
    rid = resource["id"]
    return {
        "fullUrl": f"{rt}/{rid}",
        "resource": resource,
        "request": {"method": "PUT", "url": f"{rt}/{rid}"}
    }


def random_date(start_year=1940, end_year=2000):
    y = random.randint(start_year, end_year)
    m = random.randint(1, 12)
    d = random.randint(1, 28)
    return f"{y:04d}-{m:02d}-{d:02d}"


def random_datetime(year_min=2018, year_max=2025):
    y = random.randint(year_min, year_max)
    m = random.randint(1, 12)
    d = random.randint(1, 28)
    h = random.randint(6, 18)
    return f"{y:04d}-{m:02d}-{d:02d}T{h:02d}:00:00+01:00"


# ===========================================================================
#  Resource builders
# ===========================================================================

def build_juristic_person(jp_id, name, country, city):
    r = {
        "resourceType": "Organization",
        "id": jp_id,
        "identifier": [{"system": "http://www.bbmri-eric.eu/", "value": f"bbmri-eric:ID:{jp_id}"}],
        "name": name,
        "address": [{"city": city, "country": country}],
    }
    r["text"] = narrative("Organization", jp_id, f"{name}, {city}, {country}")
    return r


def build_biobank(bb_id, name, country, city, jp_ref, bbmri_id):
    caps = random.sample(INFRASTRUCTURAL_CAPABILITIES, k=random.randint(1, 3))
    r = {
        "resourceType": "Organization",
        "id": bb_id,
        "meta": {"profile": [f"{BASE}/StructureDefinition/miabis-biobank"]},
        "identifier": [{"system": "http://www.bbmri-eric.eu/", "value": f"bbmri-eric:ID:{bbmri_id}"}],
        "name": name,
        "alias": [bb_id.upper()],
        "telecom": [{"system": "url", "value": f"https://example.org/{bb_id}"}],
        "address": [{"city": city, "country": country}],
        "contact": [{
            "name": {"family": random.choice(LAST_NAMES), "given": [random.choice(FIRST_NAMES_M + FIRST_NAMES_F)]},
            "telecom": [{"system": "email", "value": f"contact@{bb_id}.example.org"}]
        }],
        "partOf": {"reference": jp_ref},
        "extension": [
            *[{
                "url": f"{BASE}/StructureDefinition/miabis-infrastructural-capabilities-extension",
                "valueCodeableConcept": {"coding": [{"system": f"{BASE}/CodeSystem/miabis-infrastructural-capabilities-cs", "code": c}]}
            } for c in caps],
            {
                "url": f"{BASE}/StructureDefinition/miabis-quality-management-standard-extension",
                "valueString": random.choice(QUALITY_STANDARDS)
            },
            {
                "url": f"{BASE}/StructureDefinition/miabis-organization-description-extension",
                "valueString": f"{name} is a biobank facility providing high-quality biospecimens and data for research."
            },
        ]
    }
    r["text"] = narrative("Organization", bb_id, f"{name}, {city}, {country}. BBMRI-ERIC ID: {bbmri_id}.")
    return r


def build_network_org(net_org_id, name, jp_ref):
    r = {
        "resourceType": "Organization",
        "id": net_org_id,
        "meta": {"profile": [f"{BASE}/StructureDefinition/miabis-network-organization"]},
        "identifier": [{"system": "http://www.bbmri-eric.eu/", "value": f"bbmri-eric:ID:{net_org_id}"}],
        "name": name,
        "partOf": {"reference": jp_ref},
        "extension": [{
            "url": f"{BASE}/StructureDefinition/miabis-organization-description-extension",
            "valueString": f"{name} coordinates biobank collaboration across multiple institutions."
        }]
    }
    r["text"] = narrative("Organization", net_org_id, name)
    return r


def build_network(net_id, net_org_ref, biobank_refs):
    r = {
        "resourceType": "Group",
        "id": net_id,
        "meta": {"profile": [f"{BASE}/StructureDefinition/miabis-network"]},
        "identifier": [{"system": "http://www.bbmri-eric.eu/", "value": f"bbmri-eric:ID:{net_id}"}],
        "active": True,
        "type": "person",
        "actual": False,
        "name": "BBMRI-ERIC Network",
        "managingEntity": {"reference": net_org_ref},
        "extension": [
            {
                "url": "http://hl7.org/fhir/5.0/StructureDefinition/extension-Group.member.entity",
                "valueReference": {"reference": ref}
            }
            for ref in biobank_refs
        ]
    }
    r["text"] = narrative("Group", net_id, f"Network with {len(biobank_refs)} biobanks.")
    return r


def build_collection_org(col_org_id, name, biobank_ref, country):
    design = random.choice(COLLECTION_DESIGNS)
    r = {
        "resourceType": "Organization",
        "id": col_org_id,
        "meta": {"profile": [f"{BASE}/StructureDefinition/miabis-collection-organization"]},
        "identifier": [{"system": "http://www.bbmri-eric.eu/", "value": f"bbmri-eric:ID:{col_org_id}"}],
        "name": name,
        "alias": [col_org_id.upper()[:10]],
        "active": True,
        "telecom": [{"system": "url", "value": f"https://example.org/{col_org_id}"}],
        "address": [{"country": country}],
        "contact": [{
            "name": {"family": random.choice(LAST_NAMES), "given": [random.choice(FIRST_NAMES_M + FIRST_NAMES_F)]},
            "telecom": [{"system": "email", "value": f"pi@{col_org_id}.example.org"}]
        }],
        "partOf": {"reference": biobank_ref},
        "extension": [
            {
                "url": f"{BASE}/StructureDefinition/miabis-organization-description-extension",
                "valueString": f"Collection of biospecimens: {name}."
            },
            {
                "url": f"{BASE}/StructureDefinition/miabis-collection-design-extension",
                "valueCodeableConcept": {"coding": [{"system": f"{BASE}/CodeSystem/miabis-collection-design-cs", "code": design}]}
            },
            {
                "url": f"{BASE}/StructureDefinition/miabis-sample-source-extension",
                "valueCodeableConcept": {"coding": [{"system": f"{BASE}/CodeSystem/miabis-sample-source-cs", "code": "Human"}]}
            },
            {
                "url": f"{BASE}/StructureDefinition/miabis-collection-dataset-type-extension",
                "valueCodeableConcept": {"coding": [{"system": f"{BASE}/CodeSystem/miabis-collection-dataset-typeCS", "code": "BiologicalSamples"}]}
            },
            {
                "url": f"{BASE}/StructureDefinition/miabis-use-and-access-conditions-extension",
                "valueCodeableConcept": {"coding": [{"system": f"{BASE}/CodeSystem/miabis-use-and-access-conditions-cs", "code": random.choice(USE_ACCESS_CONDITIONS)}]}
            },
        ]
    }
    r["text"] = narrative("Organization", col_org_id, f"{name}, part of {biobank_ref}.")
    return r


def build_collection_group(col_id, col_org_ref, specimen_refs, num_subjects, sample_type_codes):
    storage_temps = random.sample([t[0] for t in STORAGE_TEMPERATURES[:5]], k=min(2, len(STORAGE_TEMPERATURES)))
    mat_types = random.sample(COLLECTION_SAMPLE_TYPES, k=min(2, len(sample_type_codes)))

    chars = [
        # Age range
        {
            "code": {"coding": [{"system": f"{BASE}/CodeSystem/miabis-characteristicCS", "code": "Age"}]},
            "valueRange": {"low": {"value": 18, "unit": "years"}, "high": {"value": random.randint(75, 95), "unit": "years"}},
            "exclude": False
        },
        # Sex: male
        {
            "code": {"coding": [{"system": f"{BASE}/CodeSystem/miabis-characteristicCS", "code": "Sex"}]},
            "valueCodeableConcept": {"coding": [{"system": "http://hl7.org/fhir/administrative-gender", "code": "male"}]},
            "exclude": False
        },
        # Sex: female
        {
            "code": {"coding": [{"system": f"{BASE}/CodeSystem/miabis-characteristicCS", "code": "Sex"}]},
            "valueCodeableConcept": {"coding": [{"system": "http://hl7.org/fhir/administrative-gender", "code": "female"}]},
            "exclude": False
        },
    ]
    # Storage temperatures
    for st in storage_temps:
        chars.append({
            "code": {"coding": [{"system": f"{BASE}/CodeSystem/miabis-characteristicCS", "code": "StorageTemperature"}]},
            "valueCodeableConcept": {"coding": [{"system": f"{BASE}/CodeSystem/miabis-storage-temperature-cs", "code": st}]},
            "exclude": False
        })
    # Material types (use collection-level CodeSystem)
    for mt in mat_types:
        chars.append({
            "code": {"coding": [{"system": f"{BASE}/CodeSystem/miabis-characteristicCS", "code": "MaterialType"}]},
            "valueCodeableConcept": {"coding": [{"system": f"{BASE}/CodeSystem/miabis-collection-sample-type-cs", "code": mt}]},
            "exclude": False
        })
    # Diagnosis available
    chars.append({
        "code": {"coding": [{"system": f"{BASE}/CodeSystem/miabis-characteristicCS", "code": "DiagnosisAvailable"}]},
        "valueCodeableConcept": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10", "code": "C00-C97", "display": "Malignant neoplasms"}]},
        "exclude": False
    })

    r = {
        "resourceType": "Group",
        "id": col_id,
        "meta": {"profile": [f"{BASE}/StructureDefinition/miabis-collection"]},
        "identifier": [{"system": "http://www.bbmri-eric.eu/", "value": f"bbmri-eric:ID:{col_id}"}],
        "active": True,
        "type": "person",
        "actual": True,
        "name": col_id.replace("-", " ").title(),
        "managingEntity": {"reference": col_org_ref},
        "characteristic": chars,
        "extension": [
            {
                "url": f"{BASE}/StructureDefinition/miabis-number-of-subjects-extension",
                "valueInteger": num_subjects
            },
            {
                "url": f"{BASE}/StructureDefinition/miabis-inclusion-criteria-extension",
                "valueCodeableConcept": {"coding": [{"system": f"{BASE}/CodeSystem/miabis-inclusion-criteria-cs", "code": random.choice(INCLUSION_CRITERIA)}]}
            },
            # Member references to specimens
            *[{
                "url": "http://hl7.org/fhir/5.0/StructureDefinition/extension-Group.member.entity",
                "valueReference": {"reference": ref}
            } for ref in specimen_refs[:20]]  # cap at 20 to keep bundle manageable
        ]
    }
    r["text"] = narrative("Group", col_id, f"Collection with {num_subjects} subjects.")
    return r


def build_donor(donor_id, gender, birth_date, deceased_date=None):
    ds_types = random.sample(DATASET_TYPES, k=random.randint(1, 3))
    r = {
        "resourceType": "Patient",
        "id": donor_id,
        "meta": {"profile": [f"{BASE}/StructureDefinition/miabis-sample-donor"]},
        "identifier": [{"system": "http://example.org/biobank/donor-ids", "value": donor_id.upper()}],
        "gender": gender,
        "birthDate": birth_date,
        "extension": [
            {"url": f"{BASE}/StructureDefinition/miabis-dataset-type-extension", "valueCode": dt}
            for dt in ds_types
        ]
    }
    if deceased_date:
        r["deceasedDateTime"] = deceased_date
    r["text"] = narrative("Patient", donor_id, f"{gender.title()}, born {birth_date}. Datasets: {', '.join(ds_types)}.")
    return r


def build_condition(cond_id, donor_ref, icd_code, icd_display):
    r = {
        "resourceType": "Condition",
        "id": cond_id,
        "meta": {"profile": [f"{BASE}/StructureDefinition/miabis-condition"]},
        "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10", "code": icd_code, "display": icd_display}]},
        "subject": {"reference": donor_ref},
    }
    r["text"] = narrative("Condition", cond_id, f"ICD-10 {icd_code} - {icd_display}. Subject: {donor_ref}.")
    return r


def build_specimen(spec_id, donor_ref, sample_type_code, sample_type_display, body_site_code, body_site_display, collected_dt, storage_temp_code, collection_identifier):
    storage_display = dict(STORAGE_TEMPERATURES).get(storage_temp_code, storage_temp_code)
    r = {
        "resourceType": "Specimen",
        "id": spec_id,
        "meta": {"profile": [f"{BASE}/StructureDefinition/miabis-sample"]},
        "identifier": [{"system": "http://example.org/biobank/sample-ids", "value": spec_id.upper()}],
        "type": {"coding": [{"system": f"{BASE}/CodeSystem/miabis-detailed-samply-type-cs", "code": sample_type_code, "display": sample_type_display}]},
        "subject": {"reference": donor_ref},
        "collection": {
            "collectedDateTime": collected_dt,
            "bodySite": {"coding": [{"system": "http://snomed.info/sct", "code": body_site_code, "display": body_site_display}]}
        },
        "processing": [{
            "description": f"Processed and stored at {storage_display}",
            "extension": [{
                "url": f"{BASE}/StructureDefinition/miabis-sample-storage-temperature-extension",
                "valueCodeableConcept": {"coding": [{"system": f"{BASE}/CodeSystem/miabis-storage-temperature-cs", "code": storage_temp_code, "display": storage_display}]}
            }]
        }],
        "extension": [{
            "url": f"{BASE}/StructureDefinition/miabis-sample-collection-extension",
            "valueIdentifier": {"system": "https://directory.bbmri-eric.eu/", "value": collection_identifier}
        }]
    }
    r["text"] = narrative("Specimen", spec_id, f"{sample_type_display}, {body_site_display}, from {donor_ref}. Storage: {storage_display}.")
    return r


def build_diagnostic_report(dr_id, donor_ref, specimen_refs, icd_code, icd_display, effective_date, conclusion_text):
    r = {
        "resourceType": "DiagnosticReport",
        "id": dr_id,
        "status": "final",
        "code": {"coding": [{"system": "http://loinc.org", "code": "22637-3", "display": "Pathology report final diagnosis Narrative"}]},
        "subject": {"reference": donor_ref},
        "effectiveDateTime": effective_date,
        "specimen": [{"reference": ref} for ref in specimen_refs],
        "conclusion": conclusion_text,
        "conclusionCode": [{"coding": [{"system": "http://hl7.org/fhir/sid/icd-10", "code": icd_code, "display": icd_display}]}],
    }
    r["text"] = narrative("DiagnosticReport", dr_id, f"Pathology report. {conclusion_text[:80]}.")
    return r


def build_observation(obs_id, donor_ref, specimen_ref, biobank_ref, icd_code, icd_display, effective_date):
    r = {
        "resourceType": "Observation",
        "id": obs_id,
        "meta": {"profile": [f"{BASE}/StructureDefinition/miabis-observation"]},
        "status": "final",
        "code": {"coding": [{"system": "http://loinc.org", "code": "52797-8"}]},
        "subject": {"reference": donor_ref},
        "specimen": {"reference": specimen_ref},
        "effectiveDateTime": effective_date,
        "valueCodeableConcept": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10", "code": icd_code, "display": icd_display}]},
        "performer": [{"reference": biobank_ref}],
    }
    r["text"] = narrative("Observation", obs_id, f"Diagnosis for {specimen_ref}: {icd_code}.")
    return r


# ===========================================================================
#  Main generator
# ===========================================================================

def generate_bundle(num_donors, num_biobanks=1, num_collections=1, seed=None):
    if seed is not None:
        random.seed(seed)

    entries = []
    all_specimen_refs = []
    all_sample_type_codes = set()

    # --- Infrastructure: Juristic Persons ---
    countries_used = random.sample(COUNTRIES, k=min(num_biobanks, len(COUNTRIES)))
    if len(countries_used) < num_biobanks:
        countries_used = countries_used * (num_biobanks // len(countries_used) + 1)
    countries_used = countries_used[:num_biobanks]

    jp_ids = []
    bb_ids = []
    bb_refs = []

    for i in range(num_biobanks):
        country = countries_used[i]
        city = random.choice(CITIES.get(country, ["Unknown"]))
        jp_id = f"juristic-person-{country}-{i+1:03d}"
        bb_id = f"biobank-{country}-{i+1:03d}"
        bbmri_id = f"{country}_{bb_id.upper()}"
        bb_name = f"{city} {random.choice(BIOBANK_SUFFIXES)}"
        jp_name = f"{city} University"

        jp_ids.append(jp_id)
        bb_ids.append(bb_id)
        bb_refs.append(f"Organization/{bb_id}")

        entries.append(make_entry(build_juristic_person(jp_id, jp_name, country, city)))
        entries.append(make_entry(build_biobank(bb_id, bb_name, country, city, f"Organization/{jp_id}", bbmri_id)))

    # --- Network ---
    net_jp = jp_ids[0]
    net_org_id = "network-org-001"
    net_id = "network-001"
    entries.append(make_entry(build_network_org(net_org_id, "BBMRI-ERIC Network Organization", f"Organization/{net_jp}")))
    entries.append(make_entry(build_network(net_id, f"Organization/{net_org_id}", bb_refs)))

    # --- Collections ---
    col_org_ids = []
    col_ids = []
    col_identifiers = []

    for i in range(num_collections):
        bb_idx = i % num_biobanks
        bb_id = bb_ids[bb_idx]
        country = countries_used[bb_idx]
        col_name = COLLECTION_NAMES[i % len(COLLECTION_NAMES)]
        col_org_id = f"col-org-{i+1:03d}"
        col_id = f"collection-{i+1:03d}"
        col_identifier = f"bbmri-eric:ID:{bb_id}:collection:{col_id}"

        col_org_ids.append(col_org_id)
        col_ids.append(col_id)
        col_identifiers.append(col_identifier)

        entries.append(make_entry(build_collection_org(col_org_id, col_name, f"Organization/{bb_id}", country)))

    # --- Donors and their dependent resources ---
    donor_entries = []
    condition_entries = []
    specimen_entries = []
    dr_entries = []
    obs_entries = []
    collection_specimen_map = {cid: [] for cid in col_ids}

    for d in range(num_donors):
        donor_id = f"donor-{d+1:06d}"
        gender = random.choice(["male", "female"])
        birth_date = random_date(1935, 2000)
        deceased = random.random() < 0.1
        deceased_date = random_date(2020, 2025) if deceased else None

        donor_entries.append(make_entry(build_donor(donor_id, gender, birth_date, deceased_date)))

        # Condition
        icd_code, icd_display = random.choice(ICD10_CODES)
        cond_id = f"condition-{d+1:06d}"
        condition_entries.append(make_entry(build_condition(cond_id, f"Patient/{donor_id}", icd_code, icd_display)))

        # Body site from ICD code
        icd_prefix = icd_code.split(".")[0]
        bs_code = ICD10_BODYSITE.get(icd_prefix, "39607008")
        bs_display = dict(BODY_SITES).get(bs_code, "Unknown")

        # Specimens (1-3 per donor)
        num_specimens = random.randint(1, 3)
        donor_specimen_refs = []
        col_idx = d % num_collections

        for s in range(num_specimens):
            spec_id = f"sample-{d+1:06d}-{s+1:02d}"
            st_code, st_display = random.choice(SAMPLE_TYPES)
            storage_code = SAMPLE_STORAGE_MAP.get(st_code, "Other")
            collected = random_datetime(2018, 2025)
            all_sample_type_codes.add(st_code)

            spec = build_specimen(
                spec_id, f"Patient/{donor_id}", st_code, st_display,
                bs_code, bs_display, collected, storage_code,
                col_identifiers[col_idx]
            )
            specimen_entries.append(make_entry(spec))
            donor_specimen_refs.append(f"Specimen/{spec_id}")
            all_specimen_refs.append(f"Specimen/{spec_id}")
            collection_specimen_map[col_ids[col_idx]].append(f"Specimen/{spec_id}")

        # DiagnosticReport
        dr_id = f"diagreport-{d+1:06d}"
        effective_date = random_date(2018, 2025)
        conclusion = f"Histopathological examination consistent with {icd_display} ({icd_code})."
        dr_entries.append(make_entry(build_diagnostic_report(
            dr_id, f"Patient/{donor_id}", donor_specimen_refs, icd_code, icd_display, effective_date, conclusion
        )))

        # Observations (one per specimen)
        for s, spec_ref in enumerate(donor_specimen_refs):
            obs_id = f"obs-{d+1:06d}-{s+1:02d}"
            bb_ref = bb_refs[d % num_biobanks]
            obs_entries.append(make_entry(build_observation(
                obs_id, f"Patient/{donor_id}", spec_ref, bb_ref, icd_code, icd_display, effective_date
            )))

    # --- Build Collection Groups (need specimen refs) ---
    col_group_entries = []
    for i, col_id in enumerate(col_ids):
        spec_refs = collection_specimen_map[col_id]
        num_subj = len(set(
            e["resource"]["subject"]["reference"]
            for e in specimen_entries
            if e["resource"]["id"] in [r.split("/")[1] for r in spec_refs]
        ))
        col_group_entries.append(make_entry(build_collection_group(
            col_id, f"Organization/{col_org_ids[i]}", spec_refs, max(num_subj, 1), all_sample_type_codes
        )))

    # --- Assemble bundle in dependency order ---
    entries.extend(col_group_entries)
    entries.extend(donor_entries)
    entries.extend(condition_entries)
    entries.extend(specimen_entries)
    entries.extend(dr_entries)
    entries.extend(obs_entries)

    bundle = {
        "resourceType": "Bundle",
        "id": str(uuid.uuid4()),
        "type": "transaction",
        "entry": entries
    }

    return bundle


def main():
    parser = argparse.ArgumentParser(
        description="Generate a MIABIS on FHIR transaction bundle.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 generate-miabis-bundle.py --donors 10
  python3 generate-miabis-bundle.py --donors 50 --biobanks 3 --collections 5
  python3 generate-miabis-bundle.py --donors 100 --output large-bundle.json --seed 42
        """
    )
    parser.add_argument("--donors", type=int, required=True, help="Number of sample donors to generate")
    parser.add_argument("--biobanks", type=int, default=1, help="Number of biobanks (default: 1)")
    parser.add_argument("--collections", type=int, default=1, help="Number of collections (default: 1)")
    parser.add_argument("--output", type=str, default=None, help="Output file (default: miabis-bundle-<donors>donors.json)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")

    args = parser.parse_args()

    if args.output is None:
        args.output = f"miabis-bundle-{args.donors}donors.json"

    print(f"Generating MIABIS on FHIR transaction bundle...")
    print(f"  Donors:      {args.donors}")
    print(f"  Biobanks:    {args.biobanks}")
    print(f"  Collections: {args.collections}")
    print(f"  Seed:        {args.seed or 'random'}")

    bundle = generate_bundle(args.donors, args.biobanks, args.collections, args.seed)

    with open(args.output, "w") as f:
        json.dump(bundle, f, indent=2, ensure_ascii=False)

    # Stats
    type_counts = {}
    for entry in bundle["entry"]:
        rt = entry["resource"]["resourceType"]
        type_counts[rt] = type_counts.get(rt, 0) + 1

    total = len(bundle["entry"])
    print(f"\n  Output: {args.output}")
    print(f"  Total resources: {total}")
    for rt in ["Organization", "Group", "Patient", "Condition", "Specimen", "DiagnosticReport", "Observation"]:
        if rt in type_counts:
            print(f"    {rt}: {type_counts[rt]}")

    print(f"\nDone! Validate with:")
    print(f"  java -jar validator_cli.jar {args.output} \\")
    print(f"    -ig miabis-on-fhir/fsh-generated/resources \\")
    print(f"    -version 4.0.1 -allow-example-urls true \\")
    print(f"    -extension http://example.org/")


if __name__ == "__main__":
    main()
