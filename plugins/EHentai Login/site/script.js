const login_identifer = "ehentai"

function main() {
    check_login(true)
}

function set_err_msg(msg) {
    document.querySelector("#error-msg").innerHTML = msg
}

function form_status(cls, msg) {
    switch (cls) {
        case 'success':
            document.querySelector("form").classList.add("success")
            document.querySelector("form").classList.remove("error")
            document.querySelector("form").classList.remove("warning")
            break
        case 'error':
            if (!document.querySelector("#error-msg").innerHTML)
                set_err_msg("Failed to login: " + msg.toString())
            document.querySelector("form").classList.add("error")
            document.querySelector("form").classList.remove("success")
            document.querySelector("form").classList.remove("warning")
            break;
        case 'warning':
            document.querySelector("form").classList.toggle("warning")
            break;
        case 'loading':
            document.querySelector("form").classList.add("loading")
            break;
        case '!loading':
            document.querySelector("form").classList.remove("loading")
            break;
    }
}

function check_login(first_time) {
    form_status("loading")
    hpx.call_function(
        "get_login_info",
        {identifier: login_identifer},
        data => {
            let fdata = data.data
            form_status("!loading")
            if (fdata) {
                if (fdata.logged_in) {
                    form_status("success")
                    if (fdata.status.toLowerCase().indexOf("exhentai") !== -1)
                        form_status("warning")
                } 
                else
                    if (!first_time){
                        set_err_msg(fdata.status)
                        form_status("error")
                    }
            } else {
                if (!first_time) {
                    form_status("error", fdata.status)
                }
            }
        })
}

function on_login(e) {
    e.preventDefault()
    let arr = serialize_form(e.target)
    let data = {
        exhentai: false
    }
    for (var i in arr) {
        let x = arr[i]
        if ( ['ipb_member_id', 'ipb_pass_hash', 'additional'].includes(x.name)) {
            data[x.name] = x.value
        } else if (x.name == 'exhentai')
            data[x.name] = (x.value == 'on') ? true : false
    }
    if (data.ipb_member_id && data.ipb_pass_hash) {
        hpx.call_function(
            "submit_login",
            {
                identifier:login_identifer,
                credentials: data,
            })

        // submit_login is an async function so delay abit before checking if the login was successful
        // a better solution is to actually poll the command and get the result when finished, but ain't nobody got time for that
        form_status("loading")
        setTimeout(check_login, 4000)
    } else {
        form_status('error')
    }
}

// in case the document is already rendered
if (document.readyState!='loading') main();
// modern browsers
else if (document.addEventListener) document.addEventListener('DOMContentLoaded', main);
// IE <= 8
else document.attachEvent('onreadystatechange', function(){
    if (document.readyState=='complete') main();
});

// Serialize form data into an array
function serialize_form(form) {
    var field, l, s = [];
    if (typeof form == 'object' && form.nodeName == "FORM") {
        var len = form.elements.length;
        for (var i=0; i<len; i++) {
            field = form.elements[i];
            if (field.name && !field.disabled && field.type != 'file' && field.type != 'reset' && field.type != 'submit' && field.type != 'button') {
                if (field.type == 'select-multiple') {
                    l = form.elements[i].options.length; 
                    for (j=0; j<l; j++) {
                        if(field.options[j].selected)
                            s[s.length] = { name: field.name, value: field.options[j].value };
                    }
                } else if ((field.type != 'checkbox' && field.type != 'radio') || field.checked) {
                    s[s.length] = { name: field.name, value: field.value };
                }
            }
        }
    }
    return s;
}
