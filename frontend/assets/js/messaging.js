(() => {
  async function list() {
    const response = await window.SokoApi.request("conversations/");
    return (response.data.results || response.data).map((item) => ({
      ...item,
      initials: item.person?.split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "SM",
      last: item.last_message?.content || "",
      time: item.updated_at ? new Date(item.updated_at).toLocaleDateString() : "",
    }));
  }

  async function get(id) {
    return (await window.SokoApi.request(`conversations/${encodeURIComponent(id)}/`)).data;
  }

  async function send(id, text, file = null) {
    let body = { content: text };
    if (file) {
      body = new FormData();
      body.append("content", text);
      body.append("attachment", file);
    }
    return (await window.SokoApi.request(`conversations/${encodeURIComponent(id)}/messages/`, {
      method: "POST",
      body,
    })).data;
  }

  async function start(product) {
    return (await window.SokoApi.request("conversations/", {
      method: "POST",
      body: { product: product.id, recipient: product.seller_id },
    })).data;
  }

  async function startSeller(seller) {
    return (await window.SokoApi.request("conversations/", {
      method: "POST",
      body: { recipient: seller.id },
    })).data;
  }

  async function report(userId, reason = "other") {
    return window.SokoApi.request("reports/", {
      method: "POST",
      body: { target_type: "user", target_id: userId, reason },
    });
  }

  async function block(userId) {
    return window.SokoApi.request(`users/${encodeURIComponent(userId)}/block/`, { method: "POST" });
  }

  async function blockedUsers() {
    const response = await window.SokoApi.request("users/blocked/");
    return response.data.results || response.data;
  }

  window.SokoMessages = { block, blockedUsers, get, list, report, send, start, startSeller };
})();
