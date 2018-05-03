import copy

# TODO: Put xsi:schemaLocation in the XMLs

from flask import Flask, Response, request
from converters.convertlib import to_xml, ensure_list, is_null
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

_projects = None
_vos = None
_rgsummary = None


@app.route('/miscproject/xml')
def projects():
    global _projects
    if not _projects:
        _projects = get_projects()
    projects_xml = to_xml(_projects)
    return Response(projects_xml, mimetype='text/xml')

@app.route('/vosummary/xml')
def voinfo():
    global _vos
    if not _vos:
        _vos = get_vos()

    if "active" in request.args:
        vos = copy.deepcopy(_vos)
        active_value = request.args.get("active_value", "")
        if active_value == "0":
            vos["VOSummary"]["VO"] = [vo for vo in vos["VOSummary"]["VO"] if not vo["Active"]]
        elif active_value == "1":
            vos["VOSummary"]["VO"] = [vo for vo in vos["VOSummary"]["VO"] if vo["Active"]]
        else:
            # invalid arguments: no VOs for you!
            return Response("<VOSummary/>", mimetype='text/xml')
    else:
        vos = _vos
    vos_xml = to_xml(vos)
    return Response(vos_xml, mimetype='text/xml')

@app.route('/rgsummary/xml')
def resources():
    global _rgsummary
    if not _rgsummary:
        _rgsummary = get_rgsummary()

    rgsummary = {"ResourceSummary": {"ResourceGroup": []}}
    rgs = copy.deepcopy(_rgsummary["ResourceSummary"]["ResourceGroup"])
    if "active" in request.args:
        active_value = request.args.get("active_value", "")
        if active_value == "0":
            for rg in rgs:
                rg["Resources"]["Resource"] = [r for r in ensure_list(rg["Resources"]["Resource"]) if not r["Active"]]
        elif active_value == "1":
            for rg in rgs:
                rg["Resources"]["Resource"] = [r for r in ensure_list(rg["Resources"]["Resource"]) if r["Active"]]
        else:
            # invalid arguments: no RGs for you!
            return Response("<ResourceSummary/>", mimetype='text/xml')
    if "disable" in request.args:
        disable_value = request.args.get("disable_value", "")
        if disable_value == "0":
            for rg in rgs:
                rg["Resources"]["Resource"] = [r for r in ensure_list(rg["Resources"]["Resource"]) if not r["Disable"]]
        elif disable_value == "1":
            for rg in rgs:
                rg["Resources"]["Resource"] = [r for r in ensure_list(rg["Resources"]["Resource"]) if r["Disable"]]
        else:
            # invalid arguments: no RGs for you!
            return Response("<ResourceSummary/>", mimetype='text/xml')

    if "gridtype" in request.args:
        gridtype_1, gridtype_2 = request.args.get("gridtype_1", ""), request.args.get("gridtype_2", "")
        if gridtype_1 == "on" and gridtype_2 == "on":
            pass
        elif gridtype_1 == "on":
            rgsummary["ResourceSummary"]["ResourceGroup"] = [rg for rg in rgs if
                                                             rg["GridType"] == "OSG Production Resource"]
        elif gridtype_2 == "on":
            rgsummary["ResourceSummary"]["ResourceGroup"] = [rg for rg in rgs if
                                                             rg["GridType"] == "OSG Integration Test Bed Resource"]
        else:
            # invalid arguments: no RGs for you!
            return Response("<ResourceSummary/>", mimetype='text/xml')

    # Drop RGs with no resources
    new_rgs = rgsummary["ResourceSummary"]["ResourceGroup"]
    rgsummary["ResourceSummary"]["ResourceGroup"] = [rg for rg in new_rgs if not is_null(rg, "Resources", "Resource")]
    rgsummary_xml = to_xml(rgsummary)
    return Response(rgsummary_xml, mimetype='text/xml')

if __name__ == '__main__':
    app.run(debug=True, use_reloader=True)

