import {Search} from "../components/search.js";
import {Wrapper} from "../components/wrapper.js";

const search_data_function = async () => {
    let data = await fetch("/miscresource/json").then(d => d.json())
    return data
}

const stashcache_data_function = async () => {
    return await fetch("/resources/stashcache-files").then(d=> d.json())
}

class ResourceFile {
    constructor(name, resource) {
        this.name = name
        this.resource = resource
        this.node = document.getElementById("file-card-template").cloneNode(true)
    }
    get_node = () => {
        this.node.getElementsByClassName("Name")[0].innerText = this.name
        for(let [c, file] of Object.entries(this.resource)){
            this.populate_textarea(c, file)
        }
        this.node.hidden = false
        return this.node
    }
    copy_textarea = (textarea) => {
        textarea.select()
        textarea.setSelectionRange(0, 99999);
        document.execCommand('copy');
    }
    populate_textarea = (c, file) => {
        let container = this.node.getElementsByClassName(c)[0]
        let textarea = container.getElementsByTagName("textarea")[0]
        let copy_button = container.getElementsByTagName("button")[0]

        textarea.value = file

        copy_button.addEventListener("click", () => this.copy_textarea(textarea))

        container.hidden = false
    }
}

class ResourceFilePage {
    constructor() {
        this.data = {}
        this.search = {}
        this.wrapper = new Wrapper()
        this.current_resources = []
    }
    initialize = async () => {
        this.data = await stashcache_data_function()
        this.search = await new Search(search_data_function, this.update_resources).initialize()
        this.update_resources()
        return this
    }
    update_resources = () => {
        this.wrapper.remove_children()
        this.current_resources = this.search.filter_data(this.data)
        for(let [key, value] of Object.entries(this.current_resources)){
            let resource_node = new ResourceFile(key, value).get_node()
            if(resource_node){
                this.wrapper.node.appendChild(resource_node)
            }
        }
    }
}

const resource_file_page = new ResourceFilePage().initialize()