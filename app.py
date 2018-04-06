from flask import Flask, Response
from datetime import datetime
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
    xml = "<Projects></Projects>"
    return Response(xml, mimetype='text/xml')

@app.route('/vosummary/xml')
def voinfo():
    xml = "<VOSummary></VOSummary>"
    return Response(xml, mimetype='text/xml')

@app.route('/rgsummary/xml')
def resources():
    xml = "<ResourceSummary></ResourceSummary>"
    return Response(xml, mimetype='text/xml')

if __name__ == '__main__':
    app.run(debug=True, use_reloader=True)

