(() => {
  "use strict";

  const form = document.querySelector("#changelist-form");
  if (!form) return;

  const actionSelects = Array.from(form.querySelectorAll('select[name="action"]'));
  if (!actionSelects.length) return;

  const labels = {
    verify_organizations: {
      title: "Verify selected organizations?",
      body: "This runs the existing verification action for the selected organization accounts.",
      confirm: "Verify organizations",
      tone: "positive",
    },
    reject_organizations: {
      title: "Reject selected organizations?",
      body: "This runs the existing rejection action for the selected organization accounts.",
      confirm: "Reject organizations",
      tone: "danger",
    },
    suspend_organizations: {
      title: "Suspend selected organizations?",
      body: "This runs the existing suspension action for the selected organization accounts.",
      confirm: "Suspend organizations",
      tone: "danger",
    },
  };

  const dialog = document.createElement("dialog");
  dialog.className = "paperloop-admin-confirm";
  dialog.setAttribute("aria-labelledby", "paperloop-admin-confirm-title");
  dialog.innerHTML = `
    <div class="paperloop-admin-confirm-content">
      <span class="paperloop-admin-confirm-mark" aria-hidden="true">!</span>
      <div>
        <h2 id="paperloop-admin-confirm-title"></h2>
        <p class="paperloop-admin-confirm-copy"></p>
      </div>
    </div>
    <div class="paperloop-admin-confirm-actions">
      <button type="button" class="paperloop-admin-confirm-cancel">Cancel</button>
      <button type="button" class="paperloop-admin-confirm-submit"></button>
    </div>`;
  document.body.append(dialog);

  const title = dialog.querySelector("#paperloop-admin-confirm-title");
  const copy = dialog.querySelector(".paperloop-admin-confirm-copy");
  const cancel = dialog.querySelector(".paperloop-admin-confirm-cancel");
  const confirm = dialog.querySelector(".paperloop-admin-confirm-submit");
  let pendingAction = "";
  let confirmedAction = "";
  let submitter = null;

  const selectedAction = () => actionSelects.map((select) => select.value).find((value) => labels[value]) || "";

  form.addEventListener("submit", (event) => {
    const action = selectedAction();
    if (!action || confirmedAction === action) {
      confirmedAction = "";
      return;
    }

    event.preventDefault();
    pendingAction = action;
    submitter = event.submitter || null;
    const details = labels[action];
    title.textContent = details.title;
    copy.textContent = details.body;
    confirm.textContent = details.confirm;
    dialog.classList.toggle("is-danger", details.tone === "danger");
    if (typeof dialog.showModal === "function") dialog.showModal();
    else if (window.confirm(`${details.title}\n\n${details.body}`)) submitConfirmed();
  });

  const submitConfirmed = () => {
    confirmedAction = pendingAction;
    pendingAction = "";
    if (typeof form.requestSubmit === "function") form.requestSubmit(submitter || undefined);
    else form.submit();
  };

  cancel.addEventListener("click", () => dialog.close());
  confirm.addEventListener("click", () => {
    dialog.close();
    submitConfirmed();
  });
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
})();
