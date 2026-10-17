(function () {
  "use strict";

  var menuToggle = document.querySelector("[data-menu-toggle]");
  var sidebar = document.getElementById("primary-navigation");

  if (menuToggle && sidebar) {
    menuToggle.addEventListener("click", function () {
      var isOpen = sidebar.classList.toggle("is-open");
      menuToggle.setAttribute("aria-expanded", String(isOpen));
    });

    sidebar.addEventListener("click", function (event) {
      if (event.target.closest("a") && window.matchMedia("(max-width: 740px)").matches) {
        sidebar.classList.remove("is-open");
        menuToggle.setAttribute("aria-expanded", "false");
      }
    });
  }

  var requestForm = document.querySelector("[data-request-form]");
  var requestText = document.getElementById("request-text");
  var requestCount = document.getElementById("request-text-count");

  if (requestForm && requestText && requestCount) {
    var updateCount = function () {
      var count = requestText.value.length;
      requestCount.textContent = count + (count === 1 ? " character" : " characters");
    };
    requestText.addEventListener("input", updateCount);
    updateCount();
  }

  var approvalForm = document.querySelector("[data-approval-form]");
  var approvalAcknowledgment = document.querySelector("[data-approval-ack]");
  var approvalSubmit = document.querySelector("[data-approval-submit]");

  if (approvalForm && approvalAcknowledgment && approvalSubmit) {
    approvalAcknowledgment.addEventListener("change", function () {
      approvalSubmit.disabled = !approvalAcknowledgment.checked;
    });
  }
}());
