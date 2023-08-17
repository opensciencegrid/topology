import {remove_children} from "../util.js";

class Wrapper {
    constructor() {
        this.node = document.getElementById("wrapper")
    }
    remove_children = () => {
        remove_children(this.node)
    }
}

export {Wrapper}