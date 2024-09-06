# Run through all the FACILITY.yaml files and check that they have an institution_id field.

import yaml
import sys
import glob

def check_facility_has_institution_id(yaml_string: str):
    facility = yaml.load(yaml_string, Loader=yaml.Loader)
    if 'InstitutionID' in facility:
        return True

    print(facility)
    return False

def main():

    facility_files = glob.glob("../../../topology/**/FACILITY.yaml")
    for file in facility_files:
        with open(file, 'r') as f:
            if not check_facility_has_institution_id(f):
                print(f"{file} does not have an institution_id field.")
                sys.exit(1)

if __name__ == "__main__":
    main()
