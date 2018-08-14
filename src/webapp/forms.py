from flask_wtf import FlaskForm
from wtforms import BooleanField, SelectField, SelectMultipleField, StringField,\
    TimeField
from wtforms.ext.dateutil.fields import DateField
from wtforms.validators import InputRequired


class GenerateDowntimeForm(FlaskForm):
    scheduled = BooleanField("Scheduled", [InputRequired()], default="checked")
    severity = SelectField("Severity", [InputRequired()], choices=[
        ("Outage", "Outage"),
        ("Severe", "Severe"),
        ("Intermittent Outage", "Intermittent Outage"),
        ("No Significant Outage Expected", "No Significant Outage Expected")
    ])
    description = StringField("Description", [InputRequired()])
    start_date = DateField("Start Date", [InputRequired()])
    start_time = TimeField("Start Time", [InputRequired()])
    end_date = DateField("End Date", [InputRequired()])
    end_time = TimeField("End Time", [InputRequired()])
    services = SelectMultipleField("Services (select one or more)", [InputRequired()], choices=[])


class DowntimeResourceSelectForm(FlaskForm):
    facility = SelectField("Facility", [InputRequired()])
    resource = SelectField("Resource", [InputRequired()])

