import {remove_children} from "../util.js";
import {Wrapper} from "./wrapper.js";
import {Search} from "./search.js";

function populate_node(data, node, columns){
    for(const column of columns){
        let column_node =  node.getElementsByClassName(column["id"])[0]

        if(column_node === undefined){continue}

        column_node.parentNode.hidden = false

        if("html" in column && data[column["id"]] !== undefined && data[column["id"]] !== null){

            remove_children(column_node)

            let child = column['html'](data)
            column_node.appendChild(child)
        } else {
            if(data[column["id"]] === null ||  data[column["id"]] === undefined){
                column_node.parentNode.hidden = true
            } else {
                column_node.innerText = data[column["id"]].toString()
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

            let card_key = value['ref'].replace(/\s|\.|\\|\/|\(|\)/g, '')

            clone.setAttribute("href", "#" + card_key)
            clone.setAttribute("aria-controls", card_key)
            clone.getElementsByClassName("collapse")[0].setAttribute("id", card_key)

            this.wrapper.node.appendChild(clone)

            clone.hidden = false
        }
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
        this.search = new Search(this.get_data, this.update_data)
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

export { TablePage, Search }
