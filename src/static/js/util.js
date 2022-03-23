function tokenize_object(data){
    if (Object(data) !== data) {
        return data
    } else if (Array.isArray(data)) {
        return data.map(v => tokenize_object(v)).join(" ")
    } else {
        return Object.values(data).map(v => tokenize_object(v)).join(" ")
    }
}

function flatten(data) {
    let result = {}

    /*
    Helper to change functionality so array values have one
    value for a recurring prop rather then a new one for each array item
     */
    const add_prop = (cur, prop) => {

        // The search has reserved characters that must be removed
        let clean_prop = prop.replaceAll("/", "")

        if(clean_prop in result){
            result[clean_prop] += ", " + cur
        } else {
            result[clean_prop] = cur
        }
        return result
    }

    const recurse = (cur, prop) => {

        if (Object(cur) !== cur) {
            result = add_prop(cur, prop)
        } else if (Array.isArray(cur)) {

            if(typeof cur[0] == "object"){
                for(let i=0, l=cur.length; i<l; i++)
                    recurse(cur[i], prop );
            } else {
                result = add_prop(cur, prop)
            }

            if (cur.length == 0)
                result = add_prop([], prop)
        } else {
            var isEmpty = true;
            for (var p in cur) {
                isEmpty = false;
                recurse(cur[p], prop ? prop+"."+p : p);
            }
            if (isEmpty && prop)
                result = add_prop({}, prop)
        }
    }

    recurse(data, "");

    return result;
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

const array_to_ul = (array) => {
    let ul_node = document.createElement("ul")
    for(const v of array){
        if(typeof v == "object"){
            ul_node.appendChild(create_li("", v))
        } else {
            ul_node.appendChild(create_li(v.toString()))
        }
    }
    return ul_node
}

const object_to_ul = (object) => {
    let ul_node = document.createElement("ul")
    for(const [k, v] of Object.entries(object)){
        ul_node.appendChild(create_li(k, v))
    }
    return ul_node
}

const create_li = (text, object = undefined) => {
    let li_node = document.createElement("li")

    if(object === undefined){
        li_node.innerText = text

    } else if(Object(object) !== object) {
        let b = document.createElement("b")
        b.innerText = text
        li_node.appendChild(b)
        let span = document.createElement("span")
        span.innerText = ": " + String(object)
        li_node.appendChild(span)

    } else {
        li_node.innerText = text
        li_node.appendChild(create_ul(object))

    }

    return li_node
}

const create_ul = (object) => {
    if(object === null){
        return array_to_ul(["null"])
    } else if(object instanceof Array) {
        return array_to_ul(object)
    } else if(typeof object == "object"){
        return object_to_ul(object)
    } else {
        return array_to_ul([object.toString()])
    }
}

const remove_children = (parent) => {
    if(parent === undefined){return}
    while (parent.firstChild) {
        parent.removeChild(parent.firstChild);
    }
}


export {lod_to_ul, create_ul, remove_children, flatten, tokenize_object}