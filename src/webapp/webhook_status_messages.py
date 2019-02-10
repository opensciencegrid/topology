
dt_success = (
    "Greetings @{sender}!\n"
    "\n"
    "Your downtime update is eligible for downtime automerge!\n"
    "\n"
    "If there are no errors in the CI tests, I will approve and pull your"
    " [request]({base_sha}...{head_sha}) from `{head_label}`.\n"
    "\n"
    "-- OSG-BOT  :hourglass_flowing_sand:"
)

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
    "Just a head's up - I did not find you in our contact database;"
    " OSG Staff will need to manually review this PR.\n"
    "\n"
    "-- OSG-BOT  :dark_sunglasses:"
)


ci_success = (
    "Downtime update eligible for automerge and CI checks passed:\n"
    "Automerge Approved :+1:\n"
    "\n"
    "-- OSG-BOT"
)
    
ci_failure = (
    "Looks like the CI checks failed; OSG Staff can help investigate.\n"
    "\n"
    "-- OSG-BOT  :disappointed:"

)

merge_success = (
    "Have a nice day!  :racehorse:\n"
    "\n"
    "-- OSG-BOT"
)

merge_failure = (
    "Unexpected merge failure!\n"
    "\n"
    "{fail_message}\n"
    "\n"
    "-- OSG-BOT :confused:"
)

