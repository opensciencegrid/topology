# Run through all the FACILITY.yaml files and check that they have an institution_id field.

import yaml
import sys
import glob
import requests

export_mapping = False

# Get the list of valid institution ids
response = requests.get("https://topology-institutions.osg-htc.org/api/institution_ids")
topology_institutions = response.json()
topology_institutions_by_id = {x['id']: x for x in topology_institutions}
topology_institution_ids = {x['id'] for x in topology_institutions}

def check_facility_institution_id(yaml_string: str):

    facility = yaml.load(yaml_string, Loader=yaml.Loader)
    if 'InstitutionID' not in facility:
        raise Exception("FACILITY.yaml does not have an InstitutionID field")

    if facility['InstitutionID'] not in topology_institution_ids and facility['InstitutionID'] is not None:
        raise Exception(f"Invalid InstitutionID: {facility['InstitutionID']}")

    # If the institution id is None, then the facility should not have any resources
    if facility['InstitutionID'] is None:

        # Check that the facility does not have any resources
        # If files exist that are not 'SITE.yaml', then the facility is assumed to have resources
        folder = "/".join(yaml_string.name.split('/')[:-1])
        files_in_folder = glob.glob(f"{folder}/**/*")
        resource_files_exist = any([f for f in files_in_folder if not f.endswith("SITE.yaml")])

        if resource_files_exist:
            raise Exception("FACILITY.yaml doesn't have a InstitutionID but has resources")

def provide_human_check_interface(facility_files: list):

    facility_institution_mapping = {}
    for file in facility_files:
        with open(file, 'r') as f:
            facility_name = file.split('/')[-2]
            facility = yaml.load(f, Loader=yaml.Loader)
            facility_institution_mapping[facility_name] = topology_institutions_by_id.get(facility['InstitutionID'], {}).get('name', None)

    if export_mapping:
        with open("facility_institution_mapping.yaml", 'w') as f:
            yaml.dump(facility_institution_mapping, f)

    else:
        print(facility_institution_mapping)

def main():

    facility_files = glob.glob("../../../topology/**/FACILITY.yaml")

    # Check the files
    errors = []
    for file in facility_files:
        with open(file, 'r') as f:
            try:
                check_facility_institution_id(f)
            except Exception as e:
                errors.append((file.split("/")[-2], e))

    # Check that we have the same amount of facilities
    # This prevents the omission of a facility
    topo_facility_folders = glob.glob("../../../topology/*/")
    if len(topo_facility_folders) != len(facility_files):
        topo_facility_folders = set([x + "/FACILITY.yaml" for x in topo_facility_folders])
        facility_files = set(facility_files)
        diff = topo_facility_folders - facility_files
        errors.append(("FACILITY.yaml", f"Number of FACILITY.yaml files does not match number of topology facilities. Missing files: {diff}"))

    # Print the errors and exit if needed
    if errors:
        for error in errors:
            print(f"Error in {error[0]}: \n\t {error[1]}")
        sys.exit(1)

    provide_human_check_interface(facility_files)


if __name__ == "__main__":
    main()
