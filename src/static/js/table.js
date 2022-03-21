import {remove_children, flatten, tokenize_object} from "./util.js";

function populate_node(data, node, columns){
    for(const column of columns){
        let column_node =  node.getElementsByClassName(column["id"])[0]

        if(column_node === undefined){continue}

        if("html" in column){

            remove_children(column_node)

            let child = column['html'](data)
            column_node.appendChild(child)
        } else {
            if(data[column["id"]] === null ){
                column_node.innerText = "null"
            } else {
                column_node.innerText = data[column["id"]].toString()
            }
        }
    }
}

class Search {
    constructor(data_function, listener) {

        this.data_function = data_function
        this.listener = listener

        this.node = document.getElementById("search")
        this.error_node = document.getElementById("search-error")
        this.history_node = document.getElementById("search-history")

        this.history = undefined
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
        for(const previous_search of this.history.values()){
           let option = document.createElement("option")
            option.value = previous_search
            this.history_node.appendChild(option)
        }
    }
    load_history = () => {
        let history = window.localStorage.getItem("search-history" + window.location.pathname)

        if(history === null){
            this.history = new Set()
        } else {
            this.history = new Set(history.split(","))
        }
        this.update_history_node()
    }
    initialize = async () => {

        this.load_history()

        if(this.lunr_idx){return}

        let data = this.organize_data(await this.data_function())

        let fields = new Set()
        Object.values(data).forEach(value => fields = new Set([...Object.keys(value), ...fields]))
        fields.delete("ref")
        this.history = new Set([...fields, ...this.history])
        this.update_history_node()

        this.lunr_idx = lunr(function () {
            this.tokenizer.separator = /[\s]+/

            this.ref('ref')

            Array.from(fields.values()).sort().forEach(v => this.field(v.toLowerCase()))

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
                return table_keys.map(key => data[key])
            } catch(e) {
                this.error_node.innerText = e.message
                return []
            }
        }
    }
}

class Table {
    constructor(wrapper, data_function, columns){
        this.grid = undefined
        this.data_function = data_function
        this.wrapper = wrapper
        this.display_node = document.getElementById("display")
        this.display_modal = new bootstrap.Modal(document.getElementById("display"), {
            keyboard: true
        })
        this.columns = columns
        this.columns.push({
            hidden: true,
            id: "data",
            data: d => d
        })
    }
    initialize = async () => {
        let table = this;
        this.grid =  new gridjs.Grid({
            columns: table.columns,
            sort: true,
            className: {
                container: "table-responsive",
                table: "table table-hover",
                td: "pointer",
                paginationButton: "mt-2 mt-sm-0"
            },
            data: async () => Object.values(await table.data_function()),
            pagination: {
                enabled: true,
                limit: 50,
                buttonsCount: 1
            }
        }).render(table.wrapper.node);
        this.grid.on('rowClick', this.row_click);
    }
    update = (data) => {
        this.grid.updateConfig({
            data: data
        }).forceRender();
    }
    toggle_row = (toggled_row, data) => {
        populate_node(data, this.display_node, this.columns)
        this.display_modal.show()
    }
    row_click = async (PointerEvent, e) => {
        let data = e["cells"][e['cells'].length - 1].data
        this.toggle_row(PointerEvent.currentTarget, data)
    }
}

class CardDisplay{
    constructor(wrapper, data_function, columns) {
        this.wrapper = wrapper
        this.data_function = data_function
        this.columns = columns
        this.template_card = document.getElementById("template-card")
    }
    initialize = async () => {
        let data = await this.data_function()

        let projects = Object.values(data)

        this.update(projects)
    }
    update = async (data) => {
        this.wrapper.remove_children()

        for(const value of data){
            let clone = this.template_card.cloneNode(true)
            clone.removeAttribute('id')

            populate_node(value, clone, this.columns)

            let card_key = value['Name'].replace(/\s|\.|\\|\/|\(|\)/g, '')

            clone.setAttribute("href", "#" + card_key)
            clone.setAttribute("aria-controls", card_key)
            clone.getElementsByClassName("collapse")[0].setAttribute("id", card_key)

            this.wrapper.node.appendChild(clone)

            clone.hidden = false
        }
    }
}

class Wrapper {
    constructor() {
        this.node = document.getElementById("wrapper")
    }
    remove_children = () => {
        remove_children(this.node)
    }
}

class TablePage{
    /**
     *
     * @param data_function - async function that returns the data as a {key:value, ...}
     * @param columns - array that follows spec detailed here -> https://gridjs.io/docs/config/columns
     */
    constructor(data_function, columns) {
        this.mode = undefined
        this.data = undefined
        this.data_function = data_function
        this.columns = columns
        this.filtered_data = undefined
        this.wrapper = new Wrapper()
        this.search = new Search(this.get_data, this.update_data, this.columns)
        this.table = new Table(this.wrapper, this.get_data, this.columns)
        this.card_display = new CardDisplay(this.wrapper, this.get_data, this.columns)
        window.addEventListener("resize", this.update_width)

        this.initialize()
    }
    initialize = async () => {
        await this.update_width() // update_width ~= initialize based on width
    }
    get_data = async () => {

        if( this.data ){ return this.data }

        this.data = await this.data_function()

        this.search.initialize()

        return this.data
    }
    update_data = () => {

        let new_filtered_data = this.search.filter_data(this.data)

        if(JSON.stringify(this.filtered_data) != JSON.stringify(new_filtered_data)){
            this.filtered_data = new_filtered_data
            this.update_page_data()
        }
    }
    update_page_data = () => {
        if(this.mode == "mobile"){
            this.card_display.update(Object.values(this.filtered_data))
        } else {
            this.table.update(Object.values(this.filtered_data))
        }
    }
    update_width = async () => {
        let new_mode = window.innerWidth < 576 ? "mobile" : "desktop";
        if( new_mode != this.mode){
            this.mode = new_mode
            this.wrapper.remove_children()
            if(this.mode == "mobile"){
                await this.card_display.initialize()
            } else {
                await this.table.initialize()
            }
            this.update_data()
        }
    }
}

export { TablePage }
