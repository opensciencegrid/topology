import os
import fnmatch
import yaml

name_dict = set()  # set of country names appeared


def correction(country_name):
    # this script only solves part of the problem since it is hard to predict
    # and unify names without seeing them
    input = country_name.strip()
    name_dict.add(input)
    if input == 'Brasil':
        return ' Brazil\n'
    if input == 'CA':
        return ' Canada\n'
    if input == 'Czech Republic':
        return ' Czechia\n'
    if input == 'Korea':
        return ' South Korea\n'
    if input == 'MEXICO':
        return ' Mexico\n'
    if input == 'NL':
        return ' Netherlands\n'
    if input in ['USA', 'US', 'United States of America', 'Unites States', 'U.S.A']:
        return ' United States\n'
    if input in ['UK']:
        return ' United Kingdom\n'
    return ' ' + input + '\n'  # name is correct


for path, dirs, files in os.walk(os.path.abspath('../topology')):
    """
    This script generates a set of Country names that are present in files
    Since wrong names can be very different from official names, the script 
    modifies manually by inspecting all the wrong names and match them individually
    """
    for fname in fnmatch.filter(files, 'SITE.yaml'):
        filepath = os.path.join(path, fname)
        # yaml dump won't work since it will mess up with sequence and comments
        '''
        with open(filepath) as stream:
            try:
                data = yaml.safe_load(stream)
            except yaml.YAMLError as error:
                print(error)
        if data is not None:
            try:
                name_dict.add(data['Country'])
                unified_name = correction(data['Country'])
                data['Country'] = unified_name
                # Uncomment code below to modify changes
                # with open(filepath, 'w') as f:
                #     yaml.safe_dump(data, f)
            except KeyError:
                # some SITE.yaml files does not have country information
                continue
        '''
        modified_content = ''
        with open(filepath, 'r') as stream:
            original = stream.readlines()
            for line in original:
                if line.startswith('Country'):
                    country_name = line.split(':')[1]
                    new_line = line.replace(
                        country_name, correction(country_name))
                else:
                    new_line = line
                modified_content += new_line
        with open(filepath, 'w') as fp:
            fp.write(modified_content)
# dumping all the names we have in topology before changes are made
print(sorted(name_dict))
