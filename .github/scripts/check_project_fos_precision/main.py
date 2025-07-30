import sys
import datetime

import yaml
import requests

from field_of_science import get_id


def get_active_projects(start_date: datetime.datetime):
    response = requests.get(
        "https://elastic.osg.chtc.io/q/ospool-summary-*/_search",
        json={
					"size": 0,
					"query": {
						"range": {
							"Date": {
								"lte": int(datetime.datetime.now().timestamp() * 1000),
								"gte": int(start_date.timestamp() * 1000)
							}
						}
					},
					"aggs": {
						"bucket": {
							"terms": {
								"field": "ProjectName.keyword",
								"size": 10000
							},
							"aggs": {
								"NumJobs": {
									"sum": {
										"field": "NumJobs"
									}
								},
							}
						}
					}
				}
    )

    data = response.json()

    active_projects = [x['key'] for x in data['aggregations']['bucket']['buckets']]

    return active_projects


def has_detailed_precision(id: str):
    return get_id(id, granularity=2) is not None


def main():
    one_year_ago = datetime.datetime.now() - datetime.timedelta(days=365)
    active_project_names = get_active_projects(one_year_ago)

    print(active_project_names)

    exceptions = []
    for project_name in active_project_names:
        try:
            project_data = yaml.load(open(f"../../../projects/{project_name}.yaml"), Loader=yaml.Loader)

            if "FieldOfScienceID" not in project_data or not has_detailed_precision(project_data["FieldOfScienceID"]):
                exceptions.append(f"Project {project_name} is running in the OSPool without detailed precision.")

        except FileNotFoundError as e:
            pass


    if exceptions:
        print("\n".join(exceptions), sys.stderr)
        raise Exception("Projects without detailed precision need to be updated.")


if __name__ == "__main__":
    main()
