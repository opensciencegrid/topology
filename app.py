from flask import Flask, Response
from converters.project_yaml_to_xml import get_projects_xml
from converters.vo_yaml_to_xml import get_vos_xml
from converters.resourcegroup_yaml_to_xml import get_rgsummary_xml
app = Flask(__name__)

@app.route('/')
def homepage():

    return """
    <h1>OSG Topology Interface</h1>
    <a href="https://github.com/opensciencegrid/topology">Source Repo</a>
    """

projects_xml = None
vos_xml = None
rgsummary_xml = None


@app.route('/miscproject/xml')
def projects():
    global projects_xml

    if not projects_xml:
        projects_xml = get_projects_xml()
    return Response(projects_xml, mimetype='text/xml')

@app.route('/vosummary/xml')
def voinfo():
    global vos_xml
    if not vos_xml:
        vos_xml = get_vos_xml()
    return Response(vos_xml, mimetype='text/xml')

@app.route('/rgsummary/xml')
def resources():
    global rgsummary_xml
    if not rgsummary_xml:
        rgsummary_xml = get_rgsummary_xml()
    return Response(rgsummary_xml, mimetype='text/xml')

if __name__ == '__main__':
    app.run(debug=True, use_reloader=True)

