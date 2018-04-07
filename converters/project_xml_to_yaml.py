import anymarkup

parsed = anymarkup.parse_file('projects.xml')


for project in parsed['Projects']['Project']:
    print "Would Create file: %s.yaml" % (project['Name'])
    serialized = anymarkup.serialize(project, "yaml")
    serialized = serialized.replace("!!omap", "").strip()
    with open("projects/{0}.yaml".format(project['Name']), 'w') as f:
        f.write(serialized)
    #print project


