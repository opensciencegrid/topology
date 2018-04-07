import anymarkup
import os

to_output = {"Projects": { "Project": [] } }
projects = []

for file in os.listdir("projects"):
    project = anymarkup.parse_file("projects/{0}".format(file))
    # For some reason, it parses the yaml file as a list of dictionaries
    # Convert to a big dictionary, so it can output proper xml
    new_project = {}
    for attr in project:
        new_project.update(attr)
    projects.append(new_project)
    

to_output["Projects"]["Project"] = projects

#print projects
anymarkup.serialize_file(to_output, 'new_projects.xml')



