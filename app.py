from flask import Flask, Response
from datetime import datetime
from converters.project_yaml_to_xml import get_projects_xml
from converters.vo_yaml_to_xml import get_vos_xml
app = Flask(__name__)

@app.route('/')
def homepage():
    the_time = datetime.now().strftime("%A, %d %b %Y %l:%M %p")

    return """
    <h1>Hello heroku</h1>
    <p>It is currently {time}.</p>
    <img src="http://loremflickr.com/600/400" />
    """.format(time=the_time)



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
    xml = "<ResourceSummary></ResourceSummary>"
    return Response(xml, mimetype='text/xml')

if __name__ == '__main__':
    app.run(debug=True, use_reloader=True)

