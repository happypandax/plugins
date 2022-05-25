const login_identifer = "ehentai";

function main() {
  check_login(true);
}

function send_message(msg) {
  return fetch("/api/server/plugin/message", {
    method: "POST",
    body: JSON.stringify(msg),
  });
}

function set_err_msg(msg) {
  document.querySelector("#error-msg").innerHTML = msg;
}

function form_status(cls, msg) {
  switch (cls) {
    case "success":
      document.querySelector("form").classList.add("success");
      document.querySelector("form").classList.remove("error");
      document.querySelector("form").classList.remove("warning");
      document.querySelector("form").classList.remove("loading");
      break;
    case "error":
      if (!document.querySelector("#error-msg").innerHTML)
        set_err_msg("Failed to login: " + msg.toString());
      document.querySelector("form").classList.add("error");
      document.querySelector("form").classList.remove("success");
      document.querySelector("form").classList.remove("warning");
      document.querySelector("form").classList.remove("loading");
      break;
    case "warning":
      document.querySelector("form").classList.toggle("warning");
      document.querySelector("form").classList.remove("loading");
      break;
    case "loading":
      document.querySelector("form").classList.add("loading");
      break;
    case "!loading":
      document.querySelector("form").classList.remove("loading");
      break;
  }
}

function check_login(first_time) {
  form_status("loading");
  send_message({
    type: "check-login",
  }).then(async (r) => {
    const d = await r.json();
    if (d) {
      if (d.logged_in) {
        form_status("success");
        if (d.status.toLowerCase().indexOf("exhentai") !== -1)
          form_status("warning");
      } else if (!first_time) {
        set_err_msg(d.status ?? d.error);
        form_status("error");
      } else {
        form_status("!loading");
      }
    } else {
      if (!first_time) {
        form_status("error", r.statusText);
      }
    }
  });
}

function on_login(e) {
  e.preventDefault();
  let formData = new FormData(e.target);
  let data = {
    exhentai: false,
  };

  for (let [key, value] of formData.entries()) {
    if (key === "exhentai") {
      data.exhentai = value == "on" ? true : false;
    } else {
      data[key] = value;
    }
  }

  if (data.ipb_member_id && data.ipb_pass_hash) {
    form_status("loading");
    send_message({
      type: "login",
      data,
    })
      .then(async (r) => {
        const d = await r.json();
        console.debug({ d });
        if (d.logged_in) {
          form_status("success");
          if (d.status.toLowerCase().indexOf("exhentai") !== -1)
            form_status("warning");
        } else {
          set_err_msg(d.status ?? d.error);
          form_status("error");
        }
      })
      .catch((e) => {
        form_status("error", e.message);
      });
  } else {
    form_status("error");
  }
}

// in case the document is already rendered
if (document.readyState != "loading") main();
// modern browsers
else if (document.addEventListener)
  document.addEventListener("DOMContentLoaded", main);
// IE <= 8
else
  document.attachEvent("onreadystatechange", function () {
    if (document.readyState == "complete") main();
  });
