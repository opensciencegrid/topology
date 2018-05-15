import copy



import flask
from flask import Flask, Response
from converters.convertlib import to_xml, ensure_list, is_null
from converters.project_yaml_to_xml import get_projects
from converters.vo_yaml_to_xml import get_vos
from converters.resourcegroup_yaml_to_xml import get_rgsummary_rgdowntime
app = Flask(__name__)

@app.route('/')
def homepage():

    return """
    <h1>OSG Topology Interface</h1>
    <a href="https://github.com/opensciencegrid/topology">Source Repo</a><br/>
    <p>XML data:
        <ul>
            <li><a href="miscproject/xml">Projects data</a></li>
            <li><a href="rgsummary/xml">Resource topology data</a></li>
            <li><a href="rgdowntime/xml">Resource downtime data</a></li>
            <li><a href="vosummary/xml">Virtual Organization data</a></li>
        </ul>
    </p>
    """

_projects = None
_vos = None
_rgsummary = None
_rgdowntime = None


@app.route('/schema/<xsdfile>')
def schema(xsdfile):
    if xsdfile in ["vosummary.xsd", "rgsummary.xsd", "rgdowntime.xsd", "miscuser.xsd"]:
        with open("schema/" + xsdfile, "r") as xsdfh:
            return Response(xsdfh.read(), mimetype="text/xml")
    else:
        flask.abort(404)


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
    args = flask.request.args
    if "active" in args:
        vos = copy.deepcopy(_vos)
        active_value = args.get("active_value", "")
        if active_value == "0":
            vos["VOSummary"]["VO"] = [vo for vo in vos["VOSummary"]["VO"] if not vo["Active"]]
        elif active_value == "1":
            vos["VOSummary"]["VO"] = [vo for vo in vos["VOSummary"]["VO"] if vo["Active"]]
        else:
            return Response("Invalid arguments: active_value must be 0 or 1", status=400)
    else:
        vos = _vos
    vos_xml = to_xml(vos)
    return Response(vos_xml, mimetype='text/xml')

@app.route('/rgsummary/xml')
def resources():
    global _rgsummary, _rgdowntime
    if not _rgsummary:
        _rgsummary, _rgdowntime = get_rgsummary_rgdowntime()

    rgsummary = copy.deepcopy(_rgsummary)
    rgs = rgsummary["ResourceSummary"]["ResourceGroup"]
    args = flask.request.args
    if "active" in args:
        active_value = args.get("active_value", "")
        if active_value == "0":
            for rg in rgs:
                rg["Resources"]["Resource"] = [r for r in ensure_list(rg["Resources"]["Resource"]) if not r["Active"]]
        elif active_value == "1":
            for rg in rgs:
                rg["Resources"]["Resource"] = [r for r in ensure_list(rg["Resources"]["Resource"]) if r["Active"]]
        else:
            return Response("Invalid arguments: active_value must be 0 or 1", status=400)
    if "disable" in args:
        disable_value = args.get("disable_value", "")
        if disable_value == "0":
            for rg in rgs:
                rg["Resources"]["Resource"] = [r for r in ensure_list(rg["Resources"]["Resource"]) if not r["Disable"]]
        elif disable_value == "1":
            for rg in rgs:
                rg["Resources"]["Resource"] = [r for r in ensure_list(rg["Resources"]["Resource"]) if r["Disable"]]
        else:
            return Response("Invalid arguments: disable_value must be 0 or 1", status=400)

    if "gridtype" in args:
        gridtype_1, gridtype_2 = args.get("gridtype_1", ""), args.get("gridtype_2", "")
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
            return Response("Invalid arguments: gridtype_1 or gridtype_2 or both must be \"on\"", status=400)

    # Drop RGs with no resources
    new_rgs = rgsummary["ResourceSummary"]["ResourceGroup"]
    rgsummary["ResourceSummary"]["ResourceGroup"] = [rg for rg in new_rgs if not is_null(rg, "Resources", "Resource")]
    rgsummary_xml = to_xml(rgsummary)
    return Response(rgsummary_xml, mimetype='text/xml')


@app.route('/rgdowntime/xml')
def downtime():
    global _rgsummary, _rgdowntime
    if not _rgdowntime:
        _rgsummary, _rgdowntime = get_rgsummary_rgdowntime()
    # TODO Filter
    rgdowntime_xml = to_xml(_rgdowntime)
    return Response(rgdowntime_xml, mimetype='text/xml')


if __name__ == '__main__':
    app.run(debug=True, use_reloader=True)

