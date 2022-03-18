const lol_to_ul = (lol) => {
    let ul_node = document.createElement("ul")

    for(const inner of lol){
        let li_node = document.createElement("li")
        li_node.innerText = inner
        ul_node.appendChild(li_node)
    }

    return ul_node
}


const lod_to_ul = (lod, key) => {
    let ul_node = document.createElement("ul")

    for(const inner of lod){
        let li_node = document.createElement("li")
        li_node.innerText = inner[key]
        ul_node.appendChild(li_node)
    }

    return ul_node
}

const remove_children = (parent) => {
    while (parent.firstChild) {
        parent.removeChild(parent.firstChild);
    }
}


export {lod_to_ul, lol_to_ul, remove_children}