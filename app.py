from flask import Flask, Response, request
from converters.convertlib import to_xml
from converters.project_yaml_to_xml import get_projects
from converters.vo_yaml_to_xml import get_vos
from converters.resourcegroup_yaml_to_xml import get_rgsummary
app = Flask(__name__)

@app.route('/')
def homepage():

    return """
    <h1>OSG Topology Interface</h1>
    <a href="https://github.com/opensciencegrid/topology">Source Repo</a>
    """

projects = None
vos = None
rgsummary = None


@app.route('/miscproject/xml')
def projects():
    global projects
    if not projects:
        projects = get_projects()
    projects_xml = to_xml(projects)
    return Response(projects_xml, mimetype='text/xml')

@app.route('/vosummary/xml')
def voinfo():
    global vos
    if not vos:
        vos = get_vos()
    vos_xml = to_xml(vos)
    return Response(vos_xml, mimetype='text/xml')

@app.route('/rgsummary/xml')
def resources():
    global rgsummary
    if not rgsummary:
        rgsummary = get_rgsummary()
    rgsummary_xml = to_xml(rgsummary)
    return Response(rgsummary_xml, mimetype='text/xml')

if __name__ == '__main__':
    app.run(debug=True, use_reloader=True)

