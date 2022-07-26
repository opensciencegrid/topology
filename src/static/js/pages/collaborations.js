import {create_ul} from "../util.js";
import {TablePage} from "../components/table.js"

const data_function = async () => {
    let data = await fetch("/vosummary/json").then(d => d.json())
    return data
}

const columns = [
    {
        id: 'LongName',
        name: 'Long Name'
    }, {
        id: 'PrimaryURL',
        name: 'Primary URL'
    }, {
        id: 'FieldsOfScience',
        name: "FieldsOfScience",
        data: d => d,
        formatter: data => {
            if(!("FieldsOfScience" in data && data["FieldsOfScience"] != null)){
                return ""
            }
            let list = []
            for(const [key, value] of Object.entries(data["FieldsOfScience"])){
                list = list.concat(value["Field"])
            }
            return list.join(", ")
        },
        html: data => {
            let key = "FieldsOfScience"
            if(key in data){
                return create_ul(data[key])
            }
            let d = document.createElement("span")
            d.innerText = "null"
            return d
        }
    }, {
        id: "DataFederations",
        name: 'Data Federation',
        hidden: true,
        data: d => d,
        html: data => {
            let key = "DataFederations"
            if(key in data){
                return create_ul(data[key])
            }
            let d = document.createElement("span")
            d.innerText = "null"
            return d
        }
    }, {
        id: 'OASIS',
        name: 'Oasis',
        hidden: true,
        data: d => d,
        html: data => {
            let key = "OASIS"
            if(key in data){
                return create_ul(data[key])
            }
            let d = document.createElement("span")
            d.innerText = "null"
            return d
        }
    }, {
        id: 'Credentials',
        name: 'Credentials',
        hidden: true,
        data: d => d,
        html: data => {
            let key = "Credentials"
            if(key in data && data[key]){
                return create_ul(data[key]["TokenIssuers"]["TokenIssuer"])
            }
            let d = document.createElement("span")
            d.innerText = "null"
            return d
        }
    }
]

const page = new TablePage(data_function, columns)