// course-nav-split-v1
document.addEventListener("DOMContentLoaded", function () {
  var menuItems = [
    ["Syllabus", "syllabus.html"],
    ["Lectures", "lectures.html"],
    ["Class assignments", "class-assignments.html"],
    ["Home assignments", "home-assignments.html"],
    ["Past years", "archive.html"],
  ];

  document.querySelectorAll(".navbar-nav > .nav-item").forEach(function (item) {
    if (item.classList.contains("course-nav-split-item")) {
      return;
    }
    var toggle = item.querySelector(":scope > a.dropdown-toggle");
    var menu = item.querySelector(":scope > ul.dropdown-menu");
    if (!toggle || !menu) {
      var simple = item.querySelector(":scope > a.nav-link .menu-text");
      if (!simple || simple.textContent.trim() !== "Course") {
        return;
      }
      var courseLink = item.querySelector(":scope > a.nav-link");
      var courseHref = courseLink.getAttribute("href") || "pages/course.html";
      var prefix = courseHref.replace(/course\.html$/, "");
      item.classList.add("dropdown");
      item.innerHTML = "";
      toggle = document.createElement("a");
      toggle.className = "nav-link dropdown-toggle";
      toggle.href = "#";
      toggle.setAttribute("role", "link");
      toggle.setAttribute("data-bs-toggle", "dropdown");
      toggle.setAttribute("aria-expanded", "false");
      toggle.innerHTML = '<span class="menu-text">Course</span>';
      menu = document.createElement("ul");
      menu.className = "dropdown-menu";
      menuItems.forEach(function (entry) {
        var li = document.createElement("li");
        var a = document.createElement("a");
        a.className = "dropdown-item";
        a.href = prefix + entry[1];
        a.innerHTML = '<span class="dropdown-text">' + entry[0] + "</span>";
        li.appendChild(a);
        menu.appendChild(li);
      });
      item.appendChild(toggle);
      item.appendChild(menu);
    }
    var label = toggle.querySelector(".menu-text");
    if (!label || label.textContent.trim() !== "Course") {
      return;
    }
    var syllabusLink = menu.querySelector('a[href*="syllabus"]');
    var courseHref = syllabusLink
      ? syllabusLink.getAttribute("href").replace("syllabus.html", "course.html")
      : "pages/course.html";
    var link = document.createElement("a");
    link.className = "nav-link course-nav-main";
    link.href = courseHref;
    link.innerHTML = toggle.innerHTML;
    if (window.location.pathname.endsWith("/course.html")) {
      link.classList.add("active");
      link.setAttribute("aria-current", "page");
    }
    var caret = document.createElement("button");
    caret.type = "button";
    caret.className = "nav-link course-nav-caret dropdown-toggle";
    caret.setAttribute("data-bs-toggle", "dropdown");
    caret.setAttribute("aria-expanded", "false");
    caret.setAttribute("aria-label", "Course sections");
    if (toggle.id) {
      caret.id = toggle.id;
      menu.setAttribute("aria-labelledby", toggle.id);
    }
    toggle.replaceWith(link, caret);
    item.classList.add("course-nav-split-item");
    if (window.bootstrap && window.bootstrap.Dropdown) {
      window.bootstrap.Dropdown.getOrCreateInstance(caret);
    }
  });
});
