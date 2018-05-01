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



@app.route('/miscproject/xml')
def projects():
    xml = get_projects_xml()
    return Response(xml, mimetype='text/xml')

@app.route('/vosummary/xml')
def voinfo():
    xml = get_vos_xml()
    return Response(xml, mimetype='text/xml')

@app.route('/rgsummary/xml')
def resources():
    xml = get_rgsummary_xml()
    return Response(xml, mimetype='text/xml')

if __name__ == '__main__':
    app.run(debug=True, use_reloader=True)

