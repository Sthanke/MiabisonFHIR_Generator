#!/usr/bin/env python3
"""
MIABIS on FHIR Transaction Bundle Generator (v2 - validation-clean)

All codes verified against FSH source in BBMRI-cz/miabis-on-fhir.

Changes vs v1:
  - fullUrl uses urn:uuid: (absolute URLs as required by FHIR spec)
  - Storage temperature codes: -18to-35, -60to-85 (literal minus signs)
  - Individual sample types: WholeBlood, TissueFixed, CancerCellLine (per detailed-samply-type-cs)
  - Dataset types: use codes from miabis-dataset-type-CS (no GenomicData etc.)
  - Collection dataset types: use codes from miabis-collection-dataset-typeCS
  - Characteristic code: Diagnosis (not DiagnosisAvailable)
  - Infrastructural capabilities: only SampleStorage, DataStorage, Biosafety
  - Inclusion criteria: AgeGroup (not AgeRange), FamilialStatus (not FamiliesOfAffectedPersons)
  - Network organization: added required address + contact fields

Usage:
    python3 generate-miabis-bundle.py --donors 10
    python3 generate-miabis-bundle.py --donors 50 --output my-bundle.json
    python3 generate-miabis-bundle.py --donors 100 --biobanks 3 --collections 5
"""

import argparse, json, os, random, uuid
from pathlib import Path

BASE = "https://fhir.bbmri-eric.eu"

ICD10_CODES = [
    ("C34.1","Upper lobe, bronchus or lung"),("C34.2","Middle lobe, bronchus or lung"),
    ("C34.3","Lower lobe, bronchus or lung"),("C50.9","Breast, unspecified"),
    ("C50.4","Upper-outer quadrant of breast"),("C18.0","Caecum"),
    ("C18.2","Ascending colon"),("C18.7","Sigmoid colon"),
    ("C61","Malignant neoplasm of prostate"),("C25.0","Head of pancreas"),
    ("C56","Malignant neoplasm of ovary"),("C64","Malignant neoplasm of kidney, except renal pelvis"),
    ("C16.0","Cardia"),("C67.9","Bladder, unspecified"),("C71.9","Brain, unspecified"),
    ("C73","Malignant neoplasm of thyroid gland"),("C43.5","Malignant melanoma of trunk"),
    ("C22.0","Liver cell carcinoma"),("C15.9","Oesophagus, unspecified"),
    ("C20","Malignant neoplasm of rectum"),
]

# miabis-detailed-samply-type-cs (individual specimen types)
SAMPLE_TYPES = [
    ("TissueFreshFrozen","Tissue (fresh frozen)"),("TissueFixed","Tissue (fixed)"),
    ("WholeBlood","Whole blood"),("Plasma","Plasma"),("Serum","Serum"),
    ("DNA","DNA"),("RNA","RNA"),("BuffyCoat","Buffy coat"),
    ("Urine","Urine"),("Saliva","Saliva"),("CancerCellLine","Cancer cell lines"),
]

# miabis-collection-sample-type-cs (collection-level)
COLLECTION_SAMPLE_TYPES = [
    "TissueFrozen","TissueFFPE","Blood","Plasma","Serum","DNA",
    "RNA","BuffyCoat","Urine","Saliva","CancerCellLine",
]

# miabis-storage-temperature-cs — literal minus signs!
STORAGE_TEMPERATURES = [
    ("RT","Room temperature"),("2to10","between 2 and 10 degrees Celsius"),
    ("-18to-35","between -18 and -35 degrees Celsius"),
    ("-60to-85","between -60 and -85 degrees Celsius"),
    ("LN","liquid nitrogen, -150 to -196 degrees Celsius"),
    ("Other","any other temperature or long time storage information"),
]

SAMPLE_STORAGE_MAP = {
    "TissueFreshFrozen":"LN","TissueFixed":"RT","WholeBlood":"-18to-35",
    "Plasma":"-60to-85","Serum":"-60to-85","DNA":"-18to-35",
    "RNA":"-60to-85","BuffyCoat":"-60to-85","Urine":"-18to-35",
    "Saliva":"2to10","CancerCellLine":"LN",
}

BODY_SITES = [
    ("39607008","Lung structure"),("76752008","Breast structure"),
    ("71854001","Colon structure"),("41216001","Prostatic structure"),
    ("15776009","Pancreatic structure"),("15497006","Ovarian structure"),
    ("64033007","Kidney structure"),("69695003","Stomach structure"),
    ("89837001","Urinary bladder structure"),("12738006","Brain structure"),
    ("69748006","Thyroid structure"),("39937001","Skin structure"),
    ("10200004","Liver structure"),("32849002","Oesophageal structure"),
    ("34402009","Rectum structure"),
]

ICD10_BODYSITE = {
    "C34":"39607008","C50":"76752008","C18":"71854001","C20":"34402009",
    "C61":"41216001","C25":"15776009","C56":"15497006","C64":"64033007",
    "C16":"69695003","C67":"89837001","C71":"12738006","C73":"69748006",
    "C43":"39937001","C22":"10200004","C15":"32849002",
}

# miabis-dataset-type-CS (donor-level)
DATASET_TYPES = [
    "Lifestyle","BiologicalSamples","SurveyData","ImagingData",
    "MedicalRecords","NationalRegistries","GenealogicalRecords",
    "PhysioBiochemicalData","Other",
]

# miabis-collection-dataset-typeCS (collection-level) — note "Lifesyle" typo is from FSH source
COLLECTION_DATASET_TYPES = [
    "Lifesyle","Environmental","Physiological","Biochemical",
    "Clinical","Psychological","Genomic","Proteomic",
    "Metabolomic","BodyImage","WholeSlideImage","PhotoImage",
    "GenealogicalRecords","Other",
]

COLLECTION_DESIGNS = [
    "CaseControl","CrossSectional","LongitudinalCohort",
    "DiseaseSpecificCohort","PopulationBasedCohort","TwinStudy",
    "QualityControl","BirthCohort","RareDiseaseCollection","Other",
]

USE_ACCESS_CONDITIONS = [
    "CommercialUse","Collaboration","SpecificResearchUse",
    "GeneticDataUse","OutsideEUAccess","Xenograft","OtherAnimalWork","Other",
]

INCLUSION_CRITERIA = [
    "HealthStatus","HospitalPatient","UseOfMedication","Gravidity",
    "AgeGroup","FamilialStatus","Sex","CountryOfResidence",
    "EthnicOrigin","PopulationRepresentative","Lifestyle","Other",
]

# Only these 3 codes exist in the CS
INFRASTRUCTURAL_CAPABILITIES = ["SampleStorage","DataStorage","Biosafety"]

QUALITY_STANDARDS = ["ISO 20387","ISO 9001","ISO 15189","OECD Guidelines"]

FIRST_NAMES_M = ["Jan","Martin","Petr","Milan","Thomas","Hans","Erik","Lars","Andrei","Marco"]
FIRST_NAMES_F = ["Eva","Jana","Maria","Petra","Anna","Helga","Ingrid","Sofia","Elena","Lucia"]
LAST_NAMES = ["Novak","Svoboda","Mueller","Schmidt","Jensen","Larsson","Popov","Rossi","Silva","Patel",
              "Horvat","Kowalski","Virtanen","Dupont","Garcia","Fernandez","Bauer","Fischer","Weber","Wagner"]

COUNTRIES = ["CZ","DE","AT","SE","FI","IT","ES","FR","NL","PL","SI","PT","NO","DK","BE"]
CITIES = {
    "CZ":["Prague","Brno","Ostrava"],"DE":["Berlin","Munich","Hannover","Hamburg"],
    "AT":["Vienna","Graz","Innsbruck"],"SE":["Stockholm","Gothenburg","Uppsala"],
    "FI":["Helsinki","Turku","Tampere"],"IT":["Rome","Milan","Florence"],
    "ES":["Madrid","Barcelona","Valencia"],"FR":["Paris","Lyon","Marseille"],
    "NL":["Amsterdam","Rotterdam","Utrecht"],"PL":["Warsaw","Krakow","Gdansk"],
    "SI":["Ljubljana","Maribor"],"PT":["Lisbon","Porto"],"NO":["Oslo","Bergen"],
    "DK":["Copenhagen","Aarhus"],"BE":["Brussels","Leuven"],
}

BIOBANK_SUFFIXES = [
    "University Hospital Biobank","Cancer Research Biobank","National Biobank",
    "Medical Center Biobank","Clinical Research Biobank","Integrated Biobank",
    "Genomics & Tissue Bank","Translational Research Biobank",
]

COLLECTION_NAMES = [
    "Solid Tumors","Hematological Malignancies","Breast Cancer Cohort",
    "Lung Cancer Registry","Colorectal Cancer Study","Prostate Cancer Cohort",
    "Pancreatic Cancer Collection","Rare Tumors Collection",
    "Population Health Study","Metabolic Diseases Cohort",
    "Cardiovascular Sample Repository","Neurological Disorders Collection",
]

_UUID_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

def _uuid(rt, rid):
    return str(uuid.uuid5(_UUID_NS, f"{rt}/{rid}"))

def ref(rt, rid):
    """Return a urn:uuid: reference that matches the fullUrl of the entry for ResourceType/id."""
    return f"urn:uuid:{_uuid(rt, rid)}"

def narrative(rt, rid, summary):
    return {"status":"generated",
            "div":f'<div xmlns="http://www.w3.org/1999/xhtml"><p><b>{rt}/{rid}</b>: {summary}</p></div>'}

def make_entry(resource):
    rt = resource["resourceType"]; rid = resource["id"]
    return {"fullUrl":f"urn:uuid:{_uuid(rt,rid)}","resource":resource,
            "request":{"method":"PUT","url":f"{rt}/{rid}"}}

def rdate(y0=1940,y1=2000):
    return f"{random.randint(y0,y1):04d}-{random.randint(1,12):02d}-{random.randint(1,28):02d}"

def rdatetime(y0=2018,y1=2025):
    return f"{random.randint(y0,y1):04d}-{random.randint(1,12):02d}-{random.randint(1,28):02d}T{random.randint(6,18):02d}:00:00+01:00"

# ===========================================================================
def build_juristic_person(jp_id, name, country, city):
    r = {"resourceType":"Organization","id":jp_id,
         "identifier":[{"system":"http://www.bbmri-eric.eu/","value":f"bbmri-eric:ID:{jp_id}"}],
         "name":name,"address":[{"city":city,"country":country}]}
    r["text"] = narrative("Organization",jp_id,f"{name}, {city}, {country}")
    return r

def build_biobank(bb_id, name, country, city, jp_ref, bbmri_id):
    caps = random.sample(INFRASTRUCTURAL_CAPABILITIES, k=random.randint(1,len(INFRASTRUCTURAL_CAPABILITIES)))
    r = {"resourceType":"Organization","id":bb_id,
         "meta":{"profile":[f"{BASE}/StructureDefinition/miabis-biobank"]},
         "identifier":[{"system":"http://www.bbmri-eric.eu/","value":f"bbmri-eric:ID:{bbmri_id}"}],
         "name":name,"alias":[bb_id.upper()],
         "telecom":[{"system":"url","value":f"https://example.org/{bb_id}"}],
         "address":[{"city":city,"country":country}],
         "contact":[{"name":{"family":random.choice(LAST_NAMES),"given":[random.choice(FIRST_NAMES_M+FIRST_NAMES_F)]},
                     "telecom":[{"system":"email","value":f"contact@{bb_id}.example.org"}]}],
         "partOf":{"reference":jp_ref},
         "extension":[
             *[{"url":f"{BASE}/StructureDefinition/miabis-infrastructural-capabilities-extension",
                "valueCodeableConcept":{"coding":[{"system":f"{BASE}/CodeSystem/miabis-infrastructural-capabilities-cs","code":c}]}} for c in caps],
             {"url":f"{BASE}/StructureDefinition/miabis-quality-management-standard-extension",
              "valueString":random.choice(QUALITY_STANDARDS)},
             {"url":f"{BASE}/StructureDefinition/miabis-organization-description-extension",
              "valueString":f"{name} is a biobank facility providing high-quality biospecimens and data for research."},
         ]}
    r["text"] = narrative("Organization",bb_id,f"{name}, {city}, {country}. BBMRI-ERIC ID: {bbmri_id}.")
    return r

def build_network_org(net_org_id, name, jp_ref, country):
    r = {"resourceType":"Organization","id":net_org_id,
         "meta":{"profile":[f"{BASE}/StructureDefinition/miabis-network-organization"]},
         "identifier":[{"system":"http://www.bbmri-eric.eu/","value":f"bbmri-eric:ID:{net_org_id}"}],
         "name":name,
         "telecom":[{"system":"url","value":"https://example.org/network"}],
         "address":[{"country":country}],
         "contact":[{"name":{"family":random.choice(LAST_NAMES),"given":[random.choice(FIRST_NAMES_M+FIRST_NAMES_F)]},
                     "telecom":[{"system":"email","value":"network@example.org"}]}],
         "partOf":{"reference":jp_ref},
         "extension":[{"url":f"{BASE}/StructureDefinition/miabis-organization-description-extension",
                       "valueString":f"{name} coordinates biobank collaboration across multiple institutions."}]}
    r["text"] = narrative("Organization",net_org_id,name)
    return r

def build_network(net_id, net_org_ref, biobank_refs):
    r = {"resourceType":"Group","id":net_id,
         "meta":{"profile":[f"{BASE}/StructureDefinition/miabis-network"]},
         "identifier":[{"system":"http://www.bbmri-eric.eu/","value":f"bbmri-eric:ID:{net_id}"}],
         "active":True,"type":"person","actual":False,
         "name":"BBMRI-ERIC Network","managingEntity":{"reference":net_org_ref},
         "extension":[{"url":"http://hl7.org/fhir/5.0/StructureDefinition/extension-Group.member.entity",
                       "valueReference":{"reference":ref}} for ref in biobank_refs]}
    r["text"] = narrative("Group",net_id,f"Network with {len(biobank_refs)} biobanks.")
    return r

def build_collection_org(col_org_id, name, biobank_ref, country):
    design = random.choice(COLLECTION_DESIGNS)
    col_ds = random.choice(COLLECTION_DATASET_TYPES)
    r = {"resourceType":"Organization","id":col_org_id,
         "meta":{"profile":[f"{BASE}/StructureDefinition/miabis-collection-organization"]},
         "identifier":[{"system":"http://www.bbmri-eric.eu/","value":f"bbmri-eric:ID:{col_org_id}"}],
         "name":name,"alias":[col_org_id.upper()[:10]],"active":True,
         "telecom":[{"system":"url","value":f"https://example.org/{col_org_id}"}],
         "address":[{"country":country}],
         "contact":[{"name":{"family":random.choice(LAST_NAMES),"given":[random.choice(FIRST_NAMES_M+FIRST_NAMES_F)]},
                     "telecom":[{"system":"email","value":f"pi@{col_org_id}.example.org"}]}],
         "partOf":{"reference":biobank_ref},
         "extension":[
             {"url":f"{BASE}/StructureDefinition/miabis-organization-description-extension",
              "valueString":f"Collection of biospecimens: {name}."},
             {"url":f"{BASE}/StructureDefinition/miabis-collection-design-extension",
              "valueCodeableConcept":{"coding":[{"system":f"{BASE}/CodeSystem/miabis-collection-design-cs","code":design}]}},
             {"url":f"{BASE}/StructureDefinition/miabis-sample-source-extension",
              "valueCodeableConcept":{"coding":[{"system":f"{BASE}/CodeSystem/miabis-sample-source-cs","code":"Human"}]}},
             {"url":f"{BASE}/StructureDefinition/miabis-collection-dataset-type-extension",
              "valueCodeableConcept":{"coding":[{"system":f"{BASE}/CodeSystem/miabis-collection-dataset-typeCS","code":col_ds}]}},
             {"url":f"{BASE}/StructureDefinition/miabis-use-and-access-conditions-extension",
              "valueCodeableConcept":{"coding":[{"system":f"{BASE}/CodeSystem/miabis-use-and-access-conditions-cs","code":random.choice(USE_ACCESS_CONDITIONS)}]}},
         ]}
    r["text"] = narrative("Organization",col_org_id,f"{name}, part of {biobank_ref}.")
    return r

def build_collection_group(col_id, col_org_ref, specimen_refs, num_subjects, sample_type_codes):
    st_temps = random.sample([t[0] for t in STORAGE_TEMPERATURES[:5]], k=min(2,5))
    mat_types = random.sample(COLLECTION_SAMPLE_TYPES, k=min(2,len(sample_type_codes)))
    st_dict = dict(STORAGE_TEMPERATURES)
    chars = [
        {"code":{"coding":[{"system":f"{BASE}/CodeSystem/miabis-characteristicCS","code":"Age"}]},
         "valueRange":{"low":{"value":18,"unit":"years"},"high":{"value":random.randint(75,95),"unit":"years"}},
         "exclude":False},
        {"code":{"coding":[{"system":f"{BASE}/CodeSystem/miabis-characteristicCS","code":"Sex"}]},
         "valueCodeableConcept":{"coding":[{"system":"http://hl7.org/fhir/administrative-gender","code":"male"}]},
         "exclude":False},
        {"code":{"coding":[{"system":f"{BASE}/CodeSystem/miabis-characteristicCS","code":"Sex"}]},
         "valueCodeableConcept":{"coding":[{"system":"http://hl7.org/fhir/administrative-gender","code":"female"}]},
         "exclude":False},
    ]
    for st in st_temps:
        chars.append({"code":{"coding":[{"system":f"{BASE}/CodeSystem/miabis-characteristicCS","code":"StorageTemperature"}]},
                      "valueCodeableConcept":{"coding":[{"system":f"{BASE}/CodeSystem/miabis-storage-temperature-cs","code":st,"display":st_dict.get(st,st)}]},
                      "exclude":False})
    for mt in mat_types:
        chars.append({"code":{"coding":[{"system":f"{BASE}/CodeSystem/miabis-characteristicCS","code":"MaterialType"}]},
                      "valueCodeableConcept":{"coding":[{"system":f"{BASE}/CodeSystem/miabis-collection-sample-type-cs","code":mt}]},
                      "exclude":False})
    chars.append({"code":{"coding":[{"system":f"{BASE}/CodeSystem/miabis-characteristicCS","code":"Diagnosis"}]},
                  "valueCodeableConcept":{"coding":[{"system":"http://hl7.org/fhir/sid/icd-10","code":"C00-C97","display":"Malignant neoplasms"}]},
                  "exclude":False})
    r = {"resourceType":"Group","id":col_id,
         "meta":{"profile":[f"{BASE}/StructureDefinition/miabis-collection"]},
         "identifier":[{"system":"http://www.bbmri-eric.eu/","value":f"bbmri-eric:ID:{col_id}"}],
         "active":True,"type":"person","actual":True,
         "name":col_id.replace("-"," ").title(),"managingEntity":{"reference":col_org_ref},
         "characteristic":chars,
         "extension":[
             {"url":f"{BASE}/StructureDefinition/miabis-number-of-subjects-extension","valueInteger":num_subjects},
             {"url":f"{BASE}/StructureDefinition/miabis-inclusion-criteria-extension",
              "valueCodeableConcept":{"coding":[{"system":f"{BASE}/CodeSystem/miabis-inclusion-criteria-cs","code":random.choice(INCLUSION_CRITERIA)}]}},
             *[{"url":"http://hl7.org/fhir/5.0/StructureDefinition/extension-Group.member.entity",
                "valueReference":{"reference":ref}} for ref in specimen_refs[:20]]
         ]}
    r["text"] = narrative("Group",col_id,f"Collection with {num_subjects} subjects.")
    return r

def build_donor(donor_id, gender, birth_date, deceased_date=None):
    ds = random.sample(DATASET_TYPES, k=random.randint(1,3))
    r = {"resourceType":"Patient","id":donor_id,
         "meta":{"profile":[f"{BASE}/StructureDefinition/miabis-sample-donor"]},
         "identifier":[{"system":"http://example.org/biobank/donor-ids","value":donor_id.upper()}],
         "gender":gender,"birthDate":birth_date,
         "extension":[{"url":f"{BASE}/StructureDefinition/miabis-dataset-type-extension","valueCode":dt} for dt in ds]}
    if deceased_date: r["deceasedDateTime"] = deceased_date
    r["text"] = narrative("Patient",donor_id,f"{gender.title()}, born {birth_date}. Datasets: {', '.join(ds)}.")
    return r

def build_condition(cond_id, donor_ref, icd_code, icd_display):
    r = {"resourceType":"Condition","id":cond_id,
         "meta":{"profile":[f"{BASE}/StructureDefinition/miabis-condition"]},
         "code":{"coding":[{"system":"http://hl7.org/fhir/sid/icd-10","code":icd_code,"display":icd_display}]},
         "subject":{"reference":donor_ref}}
    r["text"] = narrative("Condition",cond_id,f"ICD-10 {icd_code} - {icd_display}. Subject: {donor_ref}.")
    return r

def build_specimen(spec_id, donor_ref, st_code, st_display, bs_code, bs_display, collected_dt, storage_code, col_id):
    st_dict = dict(STORAGE_TEMPERATURES)
    sd = st_dict.get(storage_code, storage_code)
    r = {"resourceType":"Specimen","id":spec_id,
         "meta":{"profile":[f"{BASE}/StructureDefinition/miabis-sample"]},
         "identifier":[{"system":"http://example.org/biobank/sample-ids","value":spec_id.upper()}],
         "type":{"coding":[{"system":f"{BASE}/CodeSystem/miabis-detailed-samply-type-cs","code":st_code,"display":st_display}]},
         "subject":{"reference":donor_ref},
         "collection":{"collectedDateTime":collected_dt,
                       "bodySite":{"coding":[{"system":"http://snomed.info/sct","code":bs_code,"display":bs_display}]}},
         "processing":[{"description":f"Processed and stored at {sd}",
                        "extension":[{"url":f"{BASE}/StructureDefinition/miabis-sample-storage-temperature-extension",
                                      "valueCodeableConcept":{"coding":[{"system":f"{BASE}/CodeSystem/miabis-storage-temperature-cs","code":storage_code,"display":sd}]}}]}],
         "extension":[{"url":f"{BASE}/StructureDefinition/miabis-sample-collection-extension",
                       "valueIdentifier":{"system":"https://directory.bbmri-eric.eu/","value":col_id}}]}
    r["text"] = narrative("Specimen",spec_id,f"{st_display}, {bs_display}, from {donor_ref}. Storage: {sd}.")
    return r

def build_diagnostic_report(dr_id, donor_ref, specimen_refs, icd_code, icd_display, eff_date, conclusion):
    r = {"resourceType":"DiagnosticReport","id":dr_id,"status":"final",
         "code":{"coding":[{"system":"http://loinc.org","code":"22637-3","display":"Pathology report final diagnosis Narrative"}]},
         "subject":{"reference":donor_ref},"effectiveDateTime":eff_date,
         "specimen":[{"reference":ref} for ref in specimen_refs],
         "conclusion":conclusion,
         "conclusionCode":[{"coding":[{"system":"http://hl7.org/fhir/sid/icd-10","code":icd_code,"display":icd_display}]}]}
    r["text"] = narrative("DiagnosticReport",dr_id,f"Pathology report. {conclusion[:80]}.")
    return r

def build_observation(obs_id, donor_ref, spec_ref, bb_ref, icd_code, icd_display, eff_date):
    r = {"resourceType":"Observation","id":obs_id,
         "meta":{"profile":[f"{BASE}/StructureDefinition/miabis-observation"]},
         "status":"final","code":{"coding":[{"system":"http://loinc.org","code":"52797-8"}]},
         "subject":{"reference":donor_ref},"specimen":{"reference":spec_ref},
         "effectiveDateTime":eff_date,
         "valueCodeableConcept":{"coding":[{"system":"http://hl7.org/fhir/sid/icd-10","code":icd_code,"display":icd_display}]},
         "performer":[{"reference":bb_ref}]}
    r["text"] = narrative("Observation",obs_id,f"Diagnosis for {spec_ref}: {icd_code}.")
    return r

# ===========================================================================
def generate_bundle(num_donors, num_biobanks=1, num_collections=1, seed=None):
    if seed is not None: random.seed(seed)
    entries = []; all_specimen_refs = []; all_sample_type_codes = set()

    countries_used = random.sample(COUNTRIES, k=min(num_biobanks,len(COUNTRIES)))
    if len(countries_used) < num_biobanks:
        countries_used = (countries_used * (num_biobanks//len(countries_used)+1))[:num_biobanks]

    jp_ids=[]; bb_ids=[]; bb_refs=[]
    for i in range(num_biobanks):
        country=countries_used[i]; city=random.choice(CITIES.get(country,["Unknown"]))
        jp_id=f"juristic-person-{country}-{i+1:03d}"; bb_id=f"biobank-{country}-{i+1:03d}"
        bbmri_id=f"{country}_{bb_id.upper()}"; bb_name=f"{city} {random.choice(BIOBANK_SUFFIXES)}"
        jp_name=f"{city} University"
        jp_ids.append(jp_id); bb_ids.append(bb_id); bb_refs.append(ref("Organization",bb_id))
        entries.append(make_entry(build_juristic_person(jp_id,jp_name,country,city)))
        entries.append(make_entry(build_biobank(bb_id,bb_name,country,city,ref("Organization",jp_id),bbmri_id)))

    net_jp=jp_ids[0]; net_country=countries_used[0]
    entries.append(make_entry(build_network_org("network-org-001","BBMRI-ERIC Network Organization",ref("Organization",net_jp),net_country)))
    entries.append(make_entry(build_network("network-001",ref("Organization","network-org-001"),bb_refs)))

    col_org_ids=[]; col_ids=[]; col_identifiers=[]
    for i in range(num_collections):
        bb_idx=i%num_biobanks; bb_id=bb_ids[bb_idx]; country=countries_used[bb_idx]
        col_name=COLLECTION_NAMES[i%len(COLLECTION_NAMES)]
        col_org_id=f"col-org-{i+1:03d}"; col_id=f"collection-{i+1:03d}"
        col_identifier=f"bbmri-eric:ID:{bb_id}:collection:{col_id}"
        col_org_ids.append(col_org_id); col_ids.append(col_id); col_identifiers.append(col_identifier)
        entries.append(make_entry(build_collection_org(col_org_id,col_name,ref("Organization",bb_id),country)))

    donor_entries=[]; condition_entries=[]; specimen_entries=[]; dr_entries=[]; obs_entries=[]
    collection_specimen_map={cid:[] for cid in col_ids}

    for d in range(num_donors):
        donor_id=f"donor-{d+1:06d}"; gender=random.choice(["male","female"])
        birth_date=rdate(1935,2000); deceased=random.random()<0.1
        deceased_date=rdate(2020,2025) if deceased else None
        donor_entries.append(make_entry(build_donor(donor_id,gender,birth_date,deceased_date)))

        icd_code,icd_display=random.choice(ICD10_CODES)
        cond_id=f"condition-{d+1:06d}"
        condition_entries.append(make_entry(build_condition(cond_id,ref("Patient",donor_id),icd_code,icd_display)))

        icd_prefix=icd_code.split(".")[0]
        bs_code=ICD10_BODYSITE.get(icd_prefix,"39607008")
        bs_display=dict(BODY_SITES).get(bs_code,"Unknown")

        num_specimens=random.randint(1,3); donor_specimen_refs=[]; col_idx=d%num_collections
        for s in range(num_specimens):
            spec_id=f"sample-{d+1:06d}-{s+1:02d}"
            st_code,st_display=random.choice(SAMPLE_TYPES)
            storage_code=SAMPLE_STORAGE_MAP.get(st_code,"Other")
            collected=rdatetime(2018,2025); all_sample_type_codes.add(st_code)
            specimen_entries.append(make_entry(build_specimen(
                spec_id,ref("Patient",donor_id),st_code,st_display,bs_code,bs_display,collected,storage_code,col_identifiers[col_idx])))
            donor_specimen_refs.append(ref("Specimen",spec_id))
            all_specimen_refs.append(ref("Specimen",spec_id))
            collection_specimen_map[col_ids[col_idx]].append(ref("Specimen",spec_id))

        dr_id=f"diagreport-{d+1:06d}"; eff_date=rdate(2018,2025)
        conclusion=f"Histopathological examination consistent with {icd_display} ({icd_code})."
        dr_entries.append(make_entry(build_diagnostic_report(dr_id,ref("Patient",donor_id),donor_specimen_refs,icd_code,icd_display,eff_date,conclusion)))

        for s,spec_ref in enumerate(donor_specimen_refs):
            obs_id=f"obs-{d+1:06d}-{s+1:02d}"; bb_ref=bb_refs[d%num_biobanks]
            obs_entries.append(make_entry(build_observation(obs_id,ref("Patient",donor_id),spec_ref,bb_ref,icd_code,icd_display,eff_date)))

    col_group_entries=[]
    for i,col_id in enumerate(col_ids):
        spec_refs=collection_specimen_map[col_id]
        # Count distinct donors whose specimens are in this collection
        spec_ids_in_col = set()
        for sr in spec_refs:
            # spec_refs are now urn:uuid: strings; extract the specimen id by reversing the uuid lookup
            for e in specimen_entries:
                if e["fullUrl"] == sr:
                    spec_ids_in_col.add(e["resource"]["subject"]["reference"])
                    break
        num_subj = len(spec_ids_in_col)
        col_group_entries.append(make_entry(build_collection_group(
            col_id,ref("Organization",col_org_ids[i]),spec_refs,max(num_subj,1),all_sample_type_codes)))

    entries.extend(col_group_entries); entries.extend(donor_entries); entries.extend(condition_entries)
    entries.extend(specimen_entries); entries.extend(dr_entries); entries.extend(obs_entries)

    return {"resourceType":"Bundle","id":str(uuid.uuid4()),"type":"transaction","entry":entries}

def main():
    parser = argparse.ArgumentParser(description="Generate a MIABIS on FHIR transaction bundle.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  python generate-miabis-bundle.py --donors 10\n  python generate-miabis-bundle.py --donors 50 --biobanks 3 --collections 5\n  python generate-miabis-bundle.py --donors 100 --output my-bundle.json --seed 42")
    parser.add_argument("--donors",type=int,required=True,help="Number of sample donors")
    parser.add_argument("--biobanks",type=int,default=1,help="Number of biobanks (default: 1)")
    parser.add_argument("--collections",type=int,default=1,help="Number of collections (default: 1)")
    parser.add_argument("--output",type=str,default=None,help="Output file (default: bundles/miabis-bundle-<N>donors.json)")
    parser.add_argument("--seed",type=int,default=None,help="Random seed")
    args = parser.parse_args()

    # Default output goes into bundles/ next to this script
    if args.output is None:
        script_dir = Path(__file__).resolve().parent
        bundles_dir = script_dir / "bundles"
        bundles_dir.mkdir(exist_ok=True)
        args.output = str(bundles_dir / f"miabis-bundle-{args.donors}donors.json")

    print(f"Generating MIABIS on FHIR transaction bundle...")
    print(f"  Donors: {args.donors}  Biobanks: {args.biobanks}  Collections: {args.collections}  Seed: {args.seed or 'random'}")

    bundle = generate_bundle(args.donors, args.biobanks, args.collections, args.seed)
    with open(args.output,"w") as f: json.dump(bundle,f,indent=2,ensure_ascii=False)

    tc={}
    for e in bundle["entry"]: rt=e["resource"]["resourceType"]; tc[rt]=tc.get(rt,0)+1
    print(f"\n  Output: {args.output}  Total: {len(bundle['entry'])} resources")
    for rt in ["Organization","Group","Patient","Condition","Specimen","DiagnosticReport","Observation"]:
        if rt in tc: print(f"    {rt}: {tc[rt]}")
    print(f"\nValidate with:\n  python validate-miabis.py {args.output}")

if __name__ == "__main__":
    main()
