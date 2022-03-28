import {lod_to_ul} from "../util.js";
import {TablePage} from "../table.js"

const data_function = async () => {
    let data = await fetch("/miscresource/json").then(d => d.json())
    return data
}

const columns = [
    {
        id: 'Name',
        name: 'Name'
    }, {
        id: 'Facility',
        name: 'Facility'
    }, {
        id: 'Site',
        name: 'Site'
    }, {
        id: 'ResourceGroup',
        name: 'ResourceGroup'
    }, {
        id: "FQDN",
        name: "FDQN",
        hidden: true
    }, {
        id: 'Active',
        name: "Active",
        hidden: true
    }, {
        id: "Services",
        name: "Services",
        hidden: true, // Danger, there is a reason I don't use this
        data: d => d,
        formatter: data => {
            let node = lod_to_ul(data["Services"]["Service"], "Name")
            return gridjs.html(node.outerHTML)
        },
        html: data => {
            let node = lod_to_ul(data["Services"]["Service"], "Name")
            return node
        }
    }, {
        id: "ContactLists",
        name: "Contact Information",
        hidden: true, // Danger, there is a reason I don't use this
        data: d => d,
        formatter: (data) => {
            let node = document.createElement("ul")
            for(const inner of data["ContactLists"]["ContactList"]){
                let li_node = document.createElement("li")
                li_node.innerText = inner["ContactType"]
                node.appendChild(li_node)
            }
            return gridjs.html(node.outerHTML)
        },
        html: (data) => {
            let node = document.createElement("ul")
            for(const inner of data["ContactLists"]["ContactList"]){
                let li_node = document.createElement("li")
                li_node.innerText = inner["ContactType"]
                if( "Contacts" in inner && "Contact" in inner["Contacts"]){
                    li_node.appendChild(lod_to_ul(inner["Contacts"]["Contact"], "Name"))
                }
                node.appendChild(li_node)
            }
            return node
        }
    }, {
        id: "Description",
        name: "Description",
        hidden: true
    }
]

const resource_page = new TablePage(data_function, columns)