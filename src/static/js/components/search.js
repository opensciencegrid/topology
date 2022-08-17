import {flatten, remove_children, tokenize_object} from "../util.js";

class Search {
    constructor(data_function, listener) {

        this.data_function = data_function
        this.listener = listener

        this.node = document.getElementById("search")
        this.error_node = document.getElementById("search-error")
        this.history_node = document.getElementById("search-history")

        this.history = new Set()
        this.fields = []
        this.lunr_idx = undefined
        this.timer = undefined

        this.node.addEventListener("input", this.search)
        this.node.addEventListener("keypress", this.save_history)
    }
    search = () => {
        clearTimeout(this.timer)
        this.timer = setTimeout(this.listener, 250)
    }
    save_history = (e) => {
        if(e.keyCode == 13){
            this.history.add(this.node.value)
            window.localStorage.setItem("search-history" + window.location.pathname, [...this.history.values()].join(","))
            this.update_history_node()
        }
    }
    update_history_node = () => {
        remove_children(this.history_node)
        for(const previous_search of [...this.history.values(), ...this.fields]){
           let option = document.createElement("option")
            option.value = previous_search
            this.history_node.appendChild(option)
        }
    }
    load_history = () => {
        let history = window.localStorage.getItem("search-history" + window.location.pathname)

        if(history !== null){
            this.history = new Set(history.split(","))
        }

        this.update_history_node()
    }
    initialize = async () => {

        let search = this
        this.load_history()
        let data = this.organize_data(await this.data_function())

        // Get the data fields and load them into the search presets
        this.fields = new Set()
        Object.values(data).forEach(value => search.fields = new Set([...Object.keys(value), ...search.fields]))
        this.fields.delete("ref")
        this.fields = Array.from(search.fields.values()).sort()
        this.update_history_node()

        // Create the search object
        this.lunr_idx = lunr(function () {
            this.tokenizer.separator = /[\s]+/

            this.ref('ref')

            search.fields.forEach(v => this.field(v.toLowerCase()))

            data.forEach(function (doc) {

                let string_doc = {}
                for (const [key, value] of Object.entries(doc)) {

                    if(key == "ref"){
                        string_doc[key] = value
                    } else if(typeof value != "string"){
                        string_doc[key.toLowerCase()] = JSON.stringify(value).toLowerCase()
                    } else {
                        string_doc[key.toLowerCase()] = value.toLowerCase()
                    }
                }
                this.add(string_doc)
            }, this)
        })

        return this
    }
    /*
        Organizes a dictionary of data for the search index.

        Used to facilitate searches at various depths of nested data.
     */
    organize_data = (data) => {
        // Convert dictionary to array of dictionaries with previous keys under 'ref'
        let data_array = Object.entries(data).map(
            ([k, v], i) => {
                v['ref'] = k
                return v
            })

        data_array = data_array.reduce((array_in_progress, current_value) => {
            let flattened_data = flatten(current_value)

            let tokenized_data = Object.keys(current_value).reduce(
                (attrs, inner_key) => ({
                    ...attrs,
                    [inner_key] : tokenize_object(current_value[inner_key])
                }),
                {}
            )

            // Overwrite flat data with top level values if need be
            array_in_progress.push({...flattened_data, ...tokenized_data})

            return array_in_progress
        }, [])

        return data_array
    }
    filter_data = (data) => {
        this.error_node.innerText = ""

        if(this.node.value == ""){
            return data
        } else {
            try {
                let table_keys = this.lunr_idx.search(this.node.value.toLowerCase()).map(r => r.ref)
                const filtered = Object.keys(data)
                    .filter(key => table_keys.includes(key))
                    .reduce((obj, key) => {
                        obj[key] = data[key];
                        return obj;
                    }, {});
                return filtered
            } catch(e) {
                this.error_node.innerText = e.message
                return {}
            }
        }
    }
}

export {Search}