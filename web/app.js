const state = { session: null, chats: [], activeId: null, model: null, busy: false, toastTimer: null };
const el = (id) => document.getElementById(id);
const chatList = el("chat-list");
const welcomeView = el("welcome-view");
const conversationView = el("conversation-view");
const messagesView = el("messages");
const input = el("message-input");
const sendButton = el("send-button");
const sidebar = el("sidebar");
const scrim = el("sidebar-scrim");

function showToast(message) {
  const toast = el("toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => toast.classList.remove("show"), 4200);
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { ...(options.body ? { "Content-Type": "application/json" } : {}), ...options.headers },
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try { message = (await response.json()).detail || message; } catch { /* use fallback */ }
    if (response.status === 401) showSignin();
    throw new Error(message);
  }
  return response;
}

function showSignin() {
  el("signin-screen").classList.remove("hidden");
  el("app-shell").classList.add("auth-required");
}

function groupLabel(dateText) {
  const date = new Date(dateText);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const day = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const diff = Math.floor((today - day) / 86400000);
  if (diff <= 0) return "Today";
  if (diff === 1) return "Yesterday";
  if (diff < 7) return "Previous 7 days";
  return "Older";
}

function renderChats(filter = "") {
  const normalized = filter.trim().toLowerCase();
  const chats = state.chats.filter((chat) => chat.title.toLowerCase().includes(normalized));
  chatList.replaceChildren();
  if (!chats.length) {
    const empty = document.createElement("p");
    empty.className = "empty-history";
    empty.textContent = normalized ? "No matching chats." : "Your conversations will appear here.";
    chatList.append(empty);
    return;
  }
  let currentGroup = "";
  for (const chat of chats) {
    const group = groupLabel(chat.updated_at);
    if (group !== currentGroup) {
      const heading = document.createElement("div");
      heading.className = "chat-group";
      heading.textContent = group;
      chatList.append(heading);
      currentGroup = group;
    }
    const item = document.createElement("div");
    item.className = `chat-item${chat.id === state.activeId ? " active" : ""}`;
    item.tabIndex = 0;
    item.setAttribute("role", "button");
    item.setAttribute("aria-label", `Open chat: ${chat.title}`);
    const title = document.createElement("span");
    title.className = "chat-title";
    title.textContent = chat.title;
    const actions = document.createElement("span");
    actions.className = "chat-item-actions";
    const remove = document.createElement("button");
    remove.className = "icon-button";
    remove.title = "Delete chat";
    remove.setAttribute("aria-label", `Delete ${chat.title}`);
    remove.innerHTML = '<svg viewBox="0 0 24 24"><path d="M4 7h16M10 11v6M14 11v6M5 7l1 14h12l1-14M9 7V4h6v3"/></svg>';
    remove.addEventListener("click", (event) => { event.stopPropagation(); askDelete(chat.id); });
    actions.append(remove);
    item.append(title, actions);
    item.addEventListener("click", () => openChat(chat.id));
    item.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openChat(chat.id); }
    });
    chatList.append(item);
  }
}

async function refreshChats() {
  const response = await request("/api/chats");
  state.chats = await response.json();
  renderChats(el("chat-search").value);
}

function setActiveChat(chatId) {
  state.activeId = chatId;
  const hasMessages = messagesView.childElementCount > 0;
  welcomeView.classList.toggle("hidden", hasMessages);
  conversationView.classList.toggle("hidden", !hasMessages);
  el("delete-chat").classList.toggle("hidden", !chatId);
  renderChats(el("chat-search").value);
}

function appendMessage(role, text = "", streaming = false) {
  const row = document.createElement("article");
  row.className = `message ${role}`;
  const content = document.createElement("div");
  content.className = "message-content";
  if (role === "assistant") {
    const avatar = document.createElement("span");
    avatar.className = "message-avatar";
    avatar.setAttribute("aria-label", "NOVA");
    avatar.innerHTML = '<svg viewBox="0 0 32 32"><path d="M16 4v24M4 16h24M7.5 7.5l17 17M24.5 7.5l-17 17"/></svg>';
    row.append(avatar);
  }
  content.textContent = text;
  if (streaming && !text) {
    const dots = document.createElement("span");
    dots.className = "typing-indicator";
    dots.innerHTML = "<i></i><i></i><i></i>";
    content.append(dots);
  }
  row.append(content);
  messagesView.append(row);
  conversationView.scrollTop = conversationView.scrollHeight;
  return content;
}

async function openChat(chatId) {
  try {
    const response = await request(`/api/chats/${encodeURIComponent(chatId)}`);
    const chat = await response.json();
    state.activeId = chat.id;
    messagesView.replaceChildren();
    for (const message of chat.messages) appendMessage(message.role === "user" ? "user" : "assistant", message.content);
    setActiveChat(chat.id);
    closeSidebar();
    input.focus();
  } catch (error) { showToast(error.message); }
}

async function createChat() {
  try {
    const response = await request("/api/chats", { method: "POST" });
    const chat = await response.json();
    state.chats.unshift(chat);
    state.activeId = chat.id;
    messagesView.replaceChildren();
    setActiveChat(chat.id);
    closeSidebar();
    input.focus();
  } catch (error) { showToast(error.message); }
}

function readEvent(eventText, onEvent) {
  const data = eventText.split("\n").filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trim()).join("\n");
  if (!data) return;
  try { onEvent(JSON.parse(data)); } catch { /* ignore incomplete event */ }
}

async function sendMessage(text) {
  if (state.busy || !text.trim()) return;
  state.busy = true;
  sendButton.disabled = true;
  const userText = text.trim();
  input.value = "";
  resizeInput();
  if (!state.activeId) await createChat();
  if (!state.activeId) { state.busy = false; sendButton.disabled = false; return; }
  appendMessage("user", userText);
  welcomeView.classList.add("hidden");
  conversationView.classList.remove("hidden");
  const assistantContent = appendMessage("assistant", "", true);
  let reply = "";
  try {
    const response = await request(`/api/chats/${encodeURIComponent(state.activeId)}/messages`, {
      method: "POST",
      body: JSON.stringify({ content: userText, model: state.model }),
    });
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let failed = false;
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      let boundary;
      while ((boundary = buffer.indexOf("\n\n")) !== -1) {
        const eventText = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        readEvent(eventText, (event) => {
          if (event.type === "token") {
            reply += event.text;
            assistantContent.textContent = reply;
            conversationView.scrollTop = conversationView.scrollHeight;
          } else if (event.type === "error") {
            failed = true;
            showToast(event.message);
          } else if (event.type === "done") {
            const chat = state.chats.find((item) => item.id === state.activeId);
            if (chat) { chat.title = event.title; chat.updated_at = new Date().toISOString(); }
          }
        });
      }
      if (done) break;
    }
    if (failed || !reply) assistantContent.closest(".message").remove();
    await refreshChats();
    if (!messagesView.childElementCount) {
      welcomeView.classList.remove("hidden");
      conversationView.classList.add("hidden");
    }
  } catch (error) {
    assistantContent.closest(".message").remove();
    showToast(error.message);
    await refreshChats().catch(() => {});
  } finally {
    state.busy = false;
    sendButton.disabled = false;
    input.focus();
  }
}

function resizeInput() {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 170)}px`;
}

function askDelete(chatId = state.activeId) {
  if (!chatId) return;
  const dialog = el("delete-dialog");
  dialog.dataset.chatId = chatId;
  dialog.showModal();
}

async function deleteChat(chatId) {
  try {
    await request(`/api/chats/${encodeURIComponent(chatId)}`, { method: "DELETE" });
    state.chats = state.chats.filter((chat) => chat.id !== chatId);
    if (state.activeId === chatId) {
      state.activeId = null;
      messagesView.replaceChildren();
      setActiveChat(null);
    }
    renderChats(el("chat-search").value);
  } catch (error) { showToast(error.message); }
}

function openSidebar() { sidebar.classList.add("open"); scrim.classList.add("visible"); }
function closeSidebar() { sidebar.classList.remove("open"); scrim.classList.remove("visible"); }

async function loadModels() {
  const select = el("model-select");
  state.model = state.session.model;
  select.replaceChildren();
  const current = document.createElement("option");
  current.value = state.model;
  current.textContent = state.model;
  select.append(current);
  try {
    const response = await request("/api/models");
    const result = await response.json();
    select.replaceChildren();
    for (const modelName of result.models) {
      const option = document.createElement("option");
      option.value = modelName;
      option.textContent = modelName;
      option.selected = modelName === state.model;
      select.append(option);
    }
    if (!result.models.includes(state.model)) {
      const fallback = document.createElement("option");
      fallback.value = state.model;
      fallback.textContent = `${state.model} · configured`;
      fallback.selected = true;
      select.prepend(fallback);
    }
  } catch (error) { select.title = error.message; }
}

async function initialize() {
  try {
    const response = await request("/api/session");
    state.session = await response.json();
    if (state.session.auth_configured && !state.session.authenticated) {
      showSignin();
      const params = new URLSearchParams(location.search);
      if (params.has("signin")) showToast("Google sign-in could not be completed. Please try again.");
      return;
    }
    const user = state.session.user || { name: "NOVA user" };
    el("account-name").textContent = user.name || "NOVA user";
    el("account-mode").textContent = state.session.local_preview ? "Local preview" : (user.email || "Personal workspace");
    el("welcome-name").textContent = state.session.local_preview || !user.name ? "" : `, ${user.name.split(" ")[0]}`;
    el("avatar").textContent = (user.name || "N").trim().charAt(0).toUpperCase();
    if (user.picture) {
      const image = document.createElement("img");
      image.src = user.picture;
      image.alt = "";
      el("avatar").replaceChildren(image);
    }
    el("preview-notice").classList.toggle("hidden", !state.session.local_preview);
    el("account-action").classList.toggle("hidden", !state.session.authenticated);
    await Promise.all([refreshChats(), loadModels()]);
  } catch (error) { showToast(error.message); }
}

el("new-chat").addEventListener("click", createChat);
el("history-menu").addEventListener("click", () => refreshChats().catch((error) => showToast(error.message)));
el("chat-search").addEventListener("input", (event) => renderChats(event.target.value));
el("composer").addEventListener("submit", (event) => { event.preventDefault(); sendMessage(input.value); });
input.addEventListener("input", resizeInput);
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); sendMessage(input.value); }
});
document.querySelectorAll("[data-prompt]").forEach((button) => button.addEventListener("click", () => {
  input.value = button.dataset.prompt;
  resizeInput();
  input.focus();
  input.setSelectionRange(input.value.length, input.value.length);
}));
el("delete-chat").addEventListener("click", () => askDelete());
el("confirm-delete").addEventListener("click", (event) => {
  event.preventDefault();
  const dialog = el("delete-dialog");
  const chatId = dialog.dataset.chatId;
  dialog.close();
  deleteChat(chatId);
});
el("open-sidebar").addEventListener("click", openSidebar);
el("close-sidebar").addEventListener("click", closeSidebar);
scrim.addEventListener("click", closeSidebar);
el("account-action").addEventListener("click", () => el("account-popover").classList.toggle("hidden"));
el("signout-button").addEventListener("click", async () => {
  await request("/auth/logout", { method: "POST" });
  location.reload();
});
el("model-select").addEventListener("change", (event) => { state.model = event.target.value; });
document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); createChat(); }
  if (event.key === "Escape") closeSidebar();
});

initialize();