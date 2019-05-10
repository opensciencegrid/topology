
from .automerge_check import RC

dt_success = None

dt_not_up_to_date = (
    "Greetings @{sender},\n"
    "\n"
    "Thank you for your pull request!\n"
    "\n"
    "Your downtime update looks clean, but `{head_label}` ({head_sha})"
    " was not up-to-date with `{base_label}` ({base_sha});"
    " OSG Staff will need to manually approve this PR.\n"
    "\n"
    "-- OSG-BOT  :broken_heart:"
)

dt_not_all_checks_pass = (
    "Greetings @{sender},\n"
    "\n"
    "Thank you for your pull request.\n"
    "\n"
    "Your [requested changes]({base_sha}...{head_sha}) affect one or more"
    " downtime files, but are not eligible for downtime automerge;"
    " OSG Staff will need to manually review this PR.\n"
    "\n"
    "-- OSG-BOT  :mag:\n"
    "\n"
    "---\n"
    "\n"
    "Output from the automerge downtime check script:\n"
    "```\n"
    "{stdout}\n"
    "```\n"
    "```\n"
    "{stderr}\n"
    "```\n"
)

non_dt_contact_error = (
    "Greetings @{sender},\n"
    "\n"
    "Thank you for your pull request.\n"
    "\n"
    "Just a heads up - I did not find you in our contact database."
    " To be added, please see our [instructions for Registering Contacts]"
    "(https://opensciencegrid.org/docs/common/registration/"
    "#registering-contacts).\n"
    "\n"
    "OSG Staff will need to review this PR manually.\n"
    "\n"
    "-- OSG-BOT  :dark_sunglasses:"
)

new_org_rejected = (
    "Greetings @{sender},\n"
    "\n"
    "Thank you for your pull request.\n"
    "\n"
    "Your [requested changes]({base_sha}...{head_sha}) add a new organization"
    " to a project file; this requires manual review from OSG Staff.\n"
    "\n"
    "-- OSG-BOT  :oncoming_police_car:\n"
    "\n"
    "---\n"
    "\n"
    "Output from the automerge check script:\n"
    "```\n"
    "{stdout}\n"
    "```\n"
    "```\n"
    "{stderr}\n"
    "```\n"
)


automerge_status_messages = {
    RC.ALL_CHECKS_PASS:  dt_success,
    RC.OUT_OF_DATE_ONLY: dt_not_up_to_date,
    RC.DT_MOD_ERRORS:    dt_not_all_checks_pass,
    RC.CONTACT_ERROR:    non_dt_contact_error,
    RC.ORGS_ADDED:       new_org_rejected
}

ci_success = None

ci_failure = (
    "Greetings @{sender},\n"
    "\n"
    "Thank you for your pull request!\n"
    "\n"
    "Your downtime update looks clean, but our CI checks failed;"
    " OSG Staff will help investigate shortly.\n"
    "\n"
    "-- OSG-BOT  :disappointed:"
)

merge_success = (
    "Greetings @{sender}!\n"
    "\n"
    "Your downtime update has been approved and merged!\n"
    "\n"
    "Have a nice day!  :racehorse:\n"
    "\n"
    "-- OSG-BOT"
)

merge_failure = (
    "Unexpected merge failure!\n"
    "\n"
    "{fail_message}\n"
    "\n"
    "OSG Staff will investigate shortly.\n"
    "\n"
    "-- OSG-BOT :confused:"
)

