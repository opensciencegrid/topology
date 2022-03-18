import {remove_children} from "./util.js";

function populate_node(data, node, columns){
    columns.forEach(column => {
        let column_node =  node.getElementsByClassName(column["id"])[0]

        if("html" in column){

            remove_children(column_node)

            let child = column['html'](data)
            column_node.appendChild(child)
        } else {
            column_node.innerText = data[column["id"]].toString()
        }
    })
}

class Search {
    constructor(data_function, listener) {
        this.node = document.getElementById("search")
        this.error_node = document.getElementById("search-error")
        this.lunr_idx = undefined
        this.data_function = data_function
        this.listener = listener
        this.timer = undefined
        this.node.addEventListener("input", this.search)
    }
    search = () => {
        clearTimeout(this.timer)
        this.timer = setTimeout(this.listener, 250)
    }
    initialize = async () => {

        if(this.lunr_idx){return}

        let data = Object.entries(await this.data_function()).map(
            ([k, v], i) => {
                v['ref'] = k
                return v
            })

        this.lunr_idx = lunr(function () {
            this.tokenizer.separator = /[\s]+/

            this.ref('ref')

            Object.keys(data[0]).forEach(k => this.field(k))

            data.forEach(function (doc) {
                let string_doc = {}
                for (const [key, value] of Object.entries(doc)) {
                    if(typeof value != "string"){
                        string_doc[key] = JSON.stringify(value)
                    } else {
                        string_doc[key] = value
                    }
                }
                this.add(string_doc)
            }, this)
        })
    }
    filter_data = (data) => {
        this.error_node.innerText = ""

        if(this.node.value == ""){
            return data
        } else {
            try {
                let table_keys = this.lunr_idx.search(this.node.value).map(r => r.ref)
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
    toggle_row = (toggled_row, project) => {
        populate_node(project, this.display_node, this.columns)
        this.display_modal.show()
    }
    row_click = async (PointerEvent, e) => {
        let data = await this.data_function()
        let row_name = e["cells"][0].data
        let project = data[row_name]
        this.toggle_row(PointerEvent.currentTarget, project)
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

        for(const project of data){
            let clone = this.template_card.cloneNode(true)
            clone.removeAttribute('id')

            populate_node(project, clone, this.columns)

            let card_key = project['Name'].replace(/\s|\.|\\|\/|\(|\)/g, '')

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
