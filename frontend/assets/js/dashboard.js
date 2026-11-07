(() => {
  async function overview() {
    const data = (await window.SokoApi.request("analytics/seller/overview/")).data;
    return {
      ...data,
      activeListings: data.activeListings ?? data.active_listings ?? 0,
      views: data.views ?? data.product_views ?? 0,
      enquiries: data.enquiries ?? data.product_enquiries ?? 0,
      favourites: data.favourites ?? data.favorites ?? 0,
      uniqueVisitors: data.uniqueVisitors ?? data.unique_visitors ?? 0,
      change: data.change || "",
      topListing: (data.topListing ?? data.top_product)
        ? window.SokoProducts.normalize(data.topListing ?? data.top_product)
        : null,
      monthly: data.monthly ?? data.monthly_views ?? [],
      monthlyLabels: data.monthlyLabels ?? data.monthly_labels ?? [],
      recentActivity: data.recentActivity ?? data.recent_activity ?? [],
    };
  }

  async function notifications() {
    const response = await window.SokoApi.request("notifications/");
    return (response.data.results || response.data).map((item) => ({
      ...item,
      title: item.title || item.subject || "SokoMtaani update",
      text: item.text || item.message || "",
      time: item.time || item.created_at || "",
      unread: item.unread ?? (item.is_read === false),
    }));
  }

  async function admin(resource) {
    const response = await window.SokoApi.request(`admin/${resource}/`);
    return response.data.results || response.data;
  }

  async function adminPage(resource, page = 1) {
    return (await window.SokoApi.request(`admin/${resource}/?page=${encodeURIComponent(page)}`)).data;
  }

  async function adminAnalytics(period = "30d") {
    const response = await window.SokoApi.request(`admin/analytics/?period=${encodeURIComponent(period)}`);
    return response.data;
  }

  async function updateProfile(values, seller = false) {
    const path = seller ? "sellers/me/" : "users/me/";
    return (await window.SokoApi.request(path, { method: "PATCH", body: values })).data;
  }

  async function getProfile(seller = false) {
    const path = seller ? "sellers/me/" : "users/me/";
    return (await window.SokoApi.request(path)).data;
  }

  async function savePreferences(values) {
    return (await window.SokoApi.request("notifications/preferences/", {
      method: "PATCH",
      body: values,
    })).data;
  }

  async function getPreferences() {
    return (await window.SokoApi.request("notifications/preferences/")).data;
  }

  async function markNotificationRead(id) {
    return window.SokoApi.request(`notifications/${encodeURIComponent(id)}/read/`, { method: "POST" });
  }

  async function deleteNotification(id) {
    return window.SokoApi.request(`notifications/${encodeURIComponent(id)}/`, { method: "DELETE" });
  }

  async function listings() {
    const response = await window.SokoApi.request("sellers/me/products/");
    return (response.data.results || response.data).map(window.SokoProducts.normalize);
  }

  async function adminAction(resource, id, action) {
    return window.SokoApi.request(`admin/${resource}/${encodeURIComponent(id)}/actions/`, {
      method: "POST",
      body: { action },
    });
  }

  async function createAdminRecord(resource, values) {
    return window.SokoApi.request(`admin/${resource}/`, { method: "POST", body: values });
  }

  async function updateAdminRecord(resource, id, values) {
    return window.SokoApi.request(`admin/${resource}/${encodeURIComponent(id)}/`, {
      method: "PATCH",
      body: values,
    });
  }

  async function saveAdminSettings(values) {
    return window.SokoApi.request("admin/settings/", { method: "PATCH", body: values });
  }

  async function siteInfo() {
    return (await window.SokoApi.request("site-info/")).data;
  }

  async function cart() {
    const response = await window.SokoApi.request("cart/");
    return response.data.results || response.data;
  }

  async function addToCart(productId) {
    return window.SokoApi.request("cart/", { method: "POST", body: { product_id: productId } });
  }

  async function removeFromCart(productId) {
    return window.SokoApi.request(`cart/${encodeURIComponent(productId)}/`, { method: "DELETE" });
  }

  async function announcements() {
    const response = await window.SokoApi.request("announcements/");
    return response.data.results || response.data;
  }

  async function suggestCategory(values) {
    return window.SokoApi.request("category-suggestions/", { method: "POST", body: values });
  }

  async function supportConversations() {
    const response = await window.SokoApi.request("support/conversations/");
    return response.data.results || response.data;
  }

  async function createSupportConversation(subject, message) {
    return window.SokoApi.request("support/conversations/", {
      method: "POST",
      body: { subject, message },
    });
  }

  async function replyToSupport(conversationId, body) {
    return window.SokoApi.request(`support/conversations/${encodeURIComponent(conversationId)}/messages/`, {
      method: "POST",
      body: { body },
    });
  }

  async function adminMessageEvidence(reportId) {
    return (await window.SokoApi.request(`admin/message-reports/${encodeURIComponent(reportId)}/evidence/`)).data;
  }

  async function unblockUser(userId) {
    return window.SokoApi.request(`users/${encodeURIComponent(userId)}/block/`, { method: "DELETE" });
  }

  window.SokoDashboard = {
    admin,
    adminAnalytics,
    adminPage,
    adminAction,
    adminMessageEvidence,
    addToCart,
    announcements,
    cart,
    createAdminRecord,
    createSupportConversation,
    deleteNotification,
    getPreferences,
    getProfile,
    listings,
    markNotificationRead,
    notifications,
    overview,
    savePreferences,
    saveAdminSettings,
    siteInfo,
    supportConversations,
    suggestCategory,
    replyToSupport,
    removeFromCart,
    unblockUser,
    updateAdminRecord,
    updateProfile,
  };
})();
